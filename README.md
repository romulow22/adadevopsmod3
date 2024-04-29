# Jornada Digital CAIXA| Devops | #1148

## Projeto do Modulo 3: *Orquestração*

- Autor: Romulo Alves | c153824

### Descrição

A Solução proposta utiliza o Minikube como ferramenta para implementação de um cluster kubernetes onde os serviços serão executados.

Estes recursos foram projetados para configurar um ambiente de desenvolvimento  com MinIO (um servidor de armazenamento de objetos), RabbitMQ (um corretor de mensagens), Redis (um armazenamento de dados em memória), aplicações Python para produzir e consumir mensagens, e um Job para inicializar o ambiente.

As rotinas dos scripts estão descritas a seguir:

1. 'criaamb.py': configura o ambiente de serviços
2. 'producer.py': inicia o producer que gera requests aleatórios a partir da API do [Mockaroo](https://mockaroo.com/)
3. 'consumer.py': cria o consumidor de eventos, verifica se pode ser considerado fraudulento, gera o relatorio para os que foram considerados e disponibiliza pelo Minio para download

### Critérios para a flag de antifraude

1. Verifica se o cookie está vencido
2. Compara sessões entre países diferentes e timestamp menor que 2 horas 
3. Verifica se o tempo de resposta é maior que 5 segundos

### Informações importantes

- O producer faz uma consulta a API do Mockaroo a cada 60 segundos
- Devido a limitação de consultas a uma API gratuita no Mockaroo (200 requests por dia), criei 3 contas com o mesmo schema apresentado abaixo e está sendo aplicado um balanceamento de carga randômico até que o limite de todas as APIs sejam atingidas.

### Detalhamento do manifesto

Os manifestos foram divididos de acordo com o tipo de recurso, como: secrets, configmaps, pvcs, deployments, services, ingress, pvs, roles, role bindings e jobs.

Especificamente, o manifesto inclui:

*  Namespace nsadadevopsmod3.
*  Secrets para credenciais do MinIO e RabbitMQ.
*  ConfigMap para a configuração do RabbitMQ.
*  PVCs para RabbitMQ, Redis e MinIO.
*  Deployments para os serviços RabbitMQ, Redis e MinIO.
*  Services para expor RabbitMQ, Redis e MinIO dentro do cluster.
*  Ingress para rotear o tráfego externo para os serviços RabbitMQ, Redis e MinIO.
*  PV e PVC para arquivos Python.
*  Role e Role Binding para permitir a verificação do status dos Jobs.
*  Job para criar o ambiente de aplicação.
*  Deployments para aplicações Python "Producer" e "Consumer" que dependem da conclusão do Job de criação do ambiente.

Há também configurações de atraso inicial para probes, limites de recursos e solicitações para os contêineres, e outras configurações adaptadas para este ambiente de desenvolvimento específico.

### Schema Utilizado para os requests dp Producer

![mockaroo-schema](images/mockaroo-schema.png?raw=true "mockaroo-schema")


### Pré-requisitos e configuração do ambiente testado

- VM linux 2 CPU / 4GB RAM
- OS RHEL 9.3
- docker 26.0.1
- docker compose 2.26.1
- git 2.39.3
- minikube v.1.33.0

## Instruções

1. Clonar o repositório

```
git clone https://github.com/romulow22/adadevopsmod3.git
```

2. Preparar o ambiente

* Incluir os fqdns em /etc/hosts

```
sudo bash -c "echo '$(minikube ip) projadadevops.local' >> /etc/hosts"
sudo bash -c "echo '$(minikube ip) registry.local' >> /etc/hosts"
```

* Incluir o endereço do registry local como inseguro na configuração do docker

```
sudo vim /etc/docker/daemon.json
{
  "insecure-registries" : ["registry.local:5000"]
}
sudo systemctl daemon-reload
sudo systemctl restart docker
```

3. Executar o ambiente 

* Entrar na pasta do projeto

```
cd adadevopsmod3
```

* Start do minikube com os addons do registry e ingress habilitados, utilizando o docker, configurando o registry interno como inseguro e montando a pasta com os arquivos python dentro do cluster.

```
minikube start --addons=registry,ingress --driver=docker --dns-domain='projadadevops.local' --insecure-registry='localhost:5000' --mount --mount-string="$(pwd):/adadevopsmod3"
``` 

* Build das images e push para o registry

```  
sudo docker compose build --no-cache --push
```  

* Deploy do ambiente

```  
find ./templates -name '*.yml' -exec minikube kubectl -- apply -f {} \;

``` 

* Configurar o contexto do namespace criado

```  
minikube kubectl -- config set-context --current --namespace=nsadadevopsmod3
```  

* Acompanhar subida do ambiente

``` 
minikube kubectl -- get pods
``` 

* Acompanhar logs

``` 
minikube kubectl -- logs -f $(minikube kubectl -- get pods | grep criaamb | cut -d' ' -f1)
minikube kubectl -- logs -f $(minikube kubectl -- get pods | grep producerapp | cut -d' ' -f1)
minikube kubectl -- logs -f $(minikube kubectl -- get pods | grep consumer | cut -d' ' -f1)
``` 

4. Opções Extras para troubleshoot

* Acessar Dashboards

``` 
minikube addons enable dashboard
minikube addons enable metrics-server
minikube dashboard --url
``` 

* Acessar pelo browser as ferramentas

1a forma:
``` 
kubectl proxy --address localhost --port=8081
RabbitMQ: http://localhost:8081/api/v1/namespaces/nsadadevopsmod3/services/rabbitmq-service:15672/proxy/
Redis: http://localhost:8081/api/v1/namespaces/nsadadevopsmod3/services/redis-service:8001/proxy/
Minio: http://localhost:8081/api/v1/namespaces/nsadadevopsmod3/services/minio-service:9001/proxy/
``` 

2a Forma:
``` 
minikube service -n nsadadevopsmod3 --all
``` 

* Acessar por curl as ferramentas

``` 
http://projadadevops.local/minio/
http://projadadevops.local/redis/
http://projadadevops.local/rabbitmq/
``` 

* Verificar imagens no repositorio

``` 
curl -X GET http://registry.local:5000/v2/_catalog
curl -X GET http://registry.local:5000/v2/adadevopsmod3/tags/list
``` 

5. Remover o laboratório.  

```
find ./templates -name '*.yml' -exec minikube kubectl -- delete -f {} \;
minikube delete --all
sudo docker rmi -f $(sudo docker images --format '{{.Repository}}:{{.Tag}}'| grep adadevopsmod3)
cd..
sudo rm -r adadevopsmod3
``` 