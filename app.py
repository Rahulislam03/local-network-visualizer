from flask import Flask, render_template, jsonify
import subprocess
import time
import concurrent.futures

app = Flask(__name__)

def ping_ip(ip):
    try:
        start_time = time.time()
        # Ping পাঠিয়া ডিভাইস সক্রিয় আছে কিনা এবং লেটেন্সি কত তা জানা
        output = subprocess.run(['ping', '-c', '1', '-w', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        latency = round((time.time() - start_time) * 1000, 2)  # Milliseconds
        
        if output.returncode == 0:
            return {'ip': ip, 'latency': latency}
    except Exception:
        pass
    return None

def scan_network_native(subnet_prefix):
    devices = []
    ip_list = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(ping_ip, ip_list)
        
        for res in results:
            if res:
                devices.append(res)
                
    return devices

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/network-data')
def get_network_data():
    subnet_prefix = '192.168.0'
    devices = scan_network_native(subnet_prefix)
    
    # Gateway Router Node (Blue color)
    nodes = [{
        'id': 'router', 
        'label': 'Gateway Router\n(192.168.0.1)', 
        'color': '#4285F4',
        'font': {'color': '#ffffff'}
    }]
    edges = []

    for idx, dev in enumerate(devices):
        if dev['ip'] == f"{subnet_prefix}.1":
            continue  # Router ইতোমধ্যে যোগ করা হয়েছে
            
        node_id = f"dev_{idx}"
        nodes.append({
            'id': node_id,
            'label': f"IP: {dev['ip']}\nPing: {dev['latency']} ms",
            'color': '#FBBC05'  # Connected device color (Yellow)
        })
        edges.append({'from': 'router', 'to': node_id})

    return jsonify({'nodes': nodes, 'edges': edges})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
