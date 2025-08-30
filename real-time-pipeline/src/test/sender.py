import json
import time
import multiprocessing
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

# AWS SQS setup
sqs = boto3.client('sqs', region_name='us-east-1', config=Config(
    retries={'max_attempts': 10, 'mode': 'standard'},
    connect_timeout=10,
    read_timeout=30
))
sts = boto3.client('sts')
account_id = sts.get_caller_identity()['Account']

QUEUE_URL = f'https://sqs.us-east-1.amazonaws.com/997118486926/ecom-rt-dev-tx'

# Constants
BATCH_SIZE = 10
LOG_INTERVALS = 20

def send_orders_from_file(file_index):
    file_path = f"sample_part_{file_index}.json"
    try:
        with open(file_path, 'r') as f:
            orders = json.load(f)
            # NEW: flatten dict-of-lists -> single list
            if isinstance(orders, dict):
                orders = orders.get("invalid", []) + orders.get("large", []) + orders.get("normal", [])
            if not isinstance(orders, list):
                raise ValueError(f"Unexpected JSON structure in {file_path}")
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}")
        return

    total_sent = 0
    next_log_at = 0
    start_time = time.time()

    # print(f"🚀 Processor-{file_index}: Sending {len(orders)} orders...\n")

    for i in range(0, len(orders), BATCH_SIZE):
        batch = orders[i:i + BATCH_SIZE]
        entries = [{
            'Id': str(idx),
            'MessageBody': json.dumps(order)
        } for idx, order in enumerate(batch)]

        try:
            response = sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=entries)
            total_sent += len(response.get('Successful', []))

            if response.get('Failed'):
                print(f"⚠️ Processor-{file_index}: Failed to send {len(response['Failed'])} messages in batch {i // BATCH_SIZE + 1}")

            progress_percent = (total_sent / len(orders)) * 100
            if progress_percent >= next_log_at:
                elapsed = time.time() - start_time
                # print(f"✅ Processor-{file_index}: [{int(progress_percent)}%] — Sent {total_sent} orders in {elapsed:.2f} sec")
                next_log_at += (100 / LOG_INTERVALS)

        except ClientError as e:
            print(f"❌ Processor-{file_index}: AWS error: {e}")
            time.sleep(1)

    total_time = time.time() - start_time
    print(f"\n🎯 Processor-{file_index}: Completed — {total_sent} orders sent in {total_time:.2f} sec")

def run_parallel_processing():
    processes = []
    for idx in range(8):  # for part_0 to part_7
        p = multiprocessing.Process(target=send_orders_from_file, args=(idx,))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

if __name__ == "__main__":
    run_parallel_processing()
