import json
import pika
import minio
import os

# Configuração do RabbitMQ
def setup_rabbitmq():
    
    exchange_name = 'transaction_exchange'
    transaction_queue_name = 'transaction_queue'
    antifraud_queue_name = 'antifraud_queue'
    routing_key = 'transaction_routing_key'
    
    # Getting Secrets
    rabbitmq_root_usr = os.getenv('RABBITMQ_ROOT_USR')
    rabbitmq_root_pwd = os.getenv('RABBITMQ_ROOT_PWD')
    rabbitmq_host = os.getenv('RABBITMQ_SERVICE_SERVICE_HOST')
    rabbitmq_port = os.getenv('RABBITMQ_SERVICE_SERVICE_PORT')
   
    credentials = pika.PlainCredentials(rabbitmq_root_usr, rabbitmq_root_pwd)
    
    connection_params = pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port, virtual_host='projetoada', credentials=credentials)
    connection = pika.BlockingConnection(connection_params)
    channel = connection.channel()
    
    # Verifica se a exchange existe
    try:
        channel.exchange_declare(exchange=exchange_name, exchange_type='direct', passive=True)
        print(f"Exchange '{exchange_name}' existe.")
    except pika.exceptions.ChannelClosedByBroker:
        # Se não existir, reabrimos o canal e declaramos a exchange
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange_name, exchange_type='direct')
        print(f"Exchange '{exchange_name}' criado.")
    
    # Verifica se a fila transaction_queue_name existe
    try:
        channel.queue_declare(queue=transaction_queue_name, passive=True)
        print(f"Queue '{transaction_queue_name}' existe.")
    except pika.exceptions.ChannelClosedByBroker:
        # Se não existir, reabrimos o canal e declaramos a fila
        channel = channel.connection.channel()
        channel.queue_declare(queue=transaction_queue_name)
        print(f"Queue '{transaction_queue_name}' criado.")

    # Verifica se a fila antifraud_queue_name existe
    try:
        channel.queue_declare(queue=antifraud_queue_name, passive=True)
        print(f"Queue '{antifraud_queue_name}' existe.")
    except pika.exceptions.ChannelClosedByBroker:
        # Se não existir, reabrimos o canal e declaramos a fila
        channel = channel.connection.channel()
        channel.queue_declare(queue=antifraud_queue_name)
        print(f"Queue '{antifraud_queue_name}' criado.")
    
    channel.queue_bind(queue=transaction_queue_name, exchange=exchange_name, routing_key=routing_key)
    channel.queue_bind(queue=antifraud_queue_name, exchange=exchange_name, routing_key=routing_key)
        
    channel.close()
    connection.close() 
    print("RabbitMQ configurado com sucesso!")
    
# Configuração do MinIO
def setup_minio():    
    bucket_name = "reportes-antifraude"
    bucket_policy = {
    "Version": "2012-10-17",
    "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            }
        ]
    }
    policy_json = json.dumps(bucket_policy)  
    
    #Getting Envs
    minio_root_usr = os.getenv('MINIO_ROOT_USR')
    minio_root_pwd = os.getenv('MINIO_ROOT_PWD')
    minio_host = os.getenv('MINIO_SERVICE_SERVICE_HOST')
    minio_port = os.getenv('MINIO_SERVICE_SERVICE_PORT_HTTP')

    client = minio.Minio(f'{minio_host}:{minio_port}', access_key=minio_root_usr, secret_key=minio_root_pwd, secure=False)
    
    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)
        print("Bucket criado com sucesso!")
    else:
        print(f"Bucket {bucket_name} já existe!")
    client.set_bucket_policy(bucket_name, policy_json)
    print("Minio configurado com sucesso!")
    
def main():
    
    setup_rabbitmq()
    setup_minio()
    print("Setup Finalizado")
    
if __name__ == "__main__":
    main()
