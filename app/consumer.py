import pika
import redis
import minio
import io
from datetime import datetime, timedelta, timezone
import json
import os

def connect_rabbitmq():
    
    # Getting Secrets
    rabbitmq_root_usr = os.getenv('RABBITMQ_ROOT_USR')
    rabbitmq_root_pwd = os.getenv('RABBITMQ_ROOT_PWD')
    rabbitmq_host = os.getenv('RABBITMQ_SERVICE_SERVICE_HOST')
    rabbitmq_port = os.getenv('RABBITMQ_SERVICE_SERVICE_PORT')
    
    credentials = pika.PlainCredentials(rabbitmq_root_usr, rabbitmq_root_pwd)
    connection_params = pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, virtual_host='projetoada', credentials=credentials)
    connection = pika.BlockingConnection(connection_params)

    return connection

# Configuração do Redis
def connect_redis():
    cache = redis.Redis(host='redis-service', port=6379, db=0, decode_responses=True)
    return cache

# Definição da regra de fraude
def is_fraudulent(event, redis_client):
    session_id = event['session_id']
    country = event['country']
    fraud_reasons = []

    # Faz o Parse do timestamp com o offset
    timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
    
    # Faz o Parse do campo cookie_expiration
    if ' UTC' in event['cookie_expiration']:
        #Assumindo que tenha UTC
        cookie_expiration_str = event['cookie_expiration'].replace(' UTC', '')
        cookie_expiration = datetime.fromisoformat(cookie_expiration_str).replace(tzinfo=timezone.utc)
    else:
        #Caso já esteja no formato ISO
        cookie_expiration = datetime.fromisoformat(event['cookie_expiration'].replace('Z', '+00:00'))
    
    if cookie_expiration < timestamp:
        fraud_reasons.append('Cookie Expirado')

    # Verifica a diferença de tempo entre sessões em países diferentes
    last_event_json = redis_client.get(session_id)
    if last_event_json:
        last_event = json.loads(last_event_json)
        last_country = last_event['country']
        last_timestamp = datetime.fromisoformat(last_event['timestamp'].replace('Z', '+00:00'))
        if last_country != country:
            time_difference = timestamp - last_timestamp
            if time_difference < timedelta(hours=2) and time_difference.total_seconds() > 0:
                fraud_reasons.append('Diferença entre paises menor que 2 horas.')
            # Caso o evento tenha vindo fora de ordem não atualiza redis  
            elif time_difference.total_seconds() < 0:
                return False, fraud_reasons

    # Verifica se o tempo de resposta é muito alto
    response_time_threshold = 5000
    if event.get('response_time', 0) > response_time_threshold:
        fraud_reasons.append('Response Time maior que 5 segundos.')

    # Atualiza o evento no Redis apenas se for mais recente que o último evento armazenado
    if not last_event_json or timestamp >= last_timestamp:
        redis_client.set(session_id, json.dumps(event))
    
    if fraud_reasons:
        return True, fraud_reasons
    else:
        return False, fraud_reasons

# Geração de relatório de fraude
def generate_fraud_report(event, fraud_reasons):
    timestamp_str = event['timestamp'].replace(':', '_').replace('-', '_').replace('T', '_').replace('Z', '')
    report_name = f"relatorio_fraude_{event['session_id']}_{timestamp_str}.txt"
    fraud_reasons_str = ', '.join(fraud_reasons)
    report_content = f"Requisição Considerada Fraudulenta:\nCategorias: {fraud_reasons_str}\nDetalhes:\n{json.dumps(event, indent=4)}"
    report_data = io.BytesIO(report_content.encode('utf-8'))
    report_size = report_data.getbuffer().nbytes
    return report_name, report_data, report_size

# Callback para processar as mensagens
def callback(ch, method, properties, body, redis_client):
    event = json.loads(body)
    fraudulent, fraud_reasons = is_fraudulent(event, redis_client)
    if fraudulent:
        print(f" [x] Requisição Fraudulenta Detectada")
        report_name, report_data, report_size = generate_fraud_report(event, fraud_reasons)
        save_file_to_minio(report_name, report_data, report_size)
    else:
        print(f" [x] Evento Processado")
    ch.basic_ack(delivery_tag=method.delivery_tag)

# Salvar file no MinIO
def save_file_to_minio(report_name, report_data, report_size):
    
    #Getting Secrets
    minio_root_usr = os.getenv('MINIO_ROOT_USR')
    minio_root_pwd = os.getenv('MINIO_ROOT_PWD')
    minio_host = os.getenv('MINIO_SERVICE_SERVICE_HOST')
    minio_port = os.getenv('MINIO_SERVICE_SERVICE_PORT_HTTP')
    
    client = minio.Minio(f'{minio_host}:{minio_port}', access_key=minio_root_usr, secret_key=minio_root_pwd, secure=False)
    bucket_name = "reportes-antifraude"
    client.put_object(bucket_name, report_name, report_data, report_size)
    report_url = client.get_presigned_url("GET", bucket_name, report_name)
    print(f" [x] Relatório de Fraude Salvo em: {report_name}")
    #print(f" >>>> URL do Report:" + report_url)
    print(f" >>>> URL do Report: " + report_url.split('?')[0].replace(f'{minio_host}:{minio_port}','projadadevops.local/minioapi'))

# Inicialização e execução do consumidor
def start_consumer(channel, redis_client):
    channel.basic_qos(prefetch_count=1)
    on_message_callback = lambda ch, method, properties, body: callback(ch, method, properties, body, redis_client)
    channel.basic_consume(queue='antifraud_queue', on_message_callback=on_message_callback, auto_ack=False)
    channel.start_consuming()

# Main
def main():
    print('Consumer iniciado...')
    connection = connect_rabbitmq()
    channel = connection.channel()
    redis_client = connect_redis()
    try:
        start_consumer(channel, redis_client)
    except KeyboardInterrupt:
        channel.stop_consuming()
    connection.close()

if __name__ == "__main__":
    main()