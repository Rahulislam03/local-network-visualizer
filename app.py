from flask import Flask, render_template, jsonify
import socket
import subprocess
import concurrent.futures

app = Flask(__name__)

def ping_ip(ip):
    # Ping পাঠিয়া ডিভাইস সক্রিয় আছে কিনা পরীক্ষা করা (অ্যান্ড্রয়েড ফ্রেন্ডলি)
    try:
        output = subprocess.run(['ping', '-c', '1', '-w', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if output.returncode == 0:
            return ip
    except Exception:
        pass
    return None

def scan_network_native(subnet_prefix):
    # ১ থেকে ২৫৪ পর্যন্ত আইপি দ্রুত স্ক্যান করার জন্য মাল্টি-থ্রেডিং ব্যবহার
    devices = []
    ip_list = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(ping_ip, ip_list)
        
        for ip in results:
            if ip:
                devices.append({'ip': ip, 'mac': 'N/A (Android Restriction)'})
                
    return devices

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/network-data')
def get_network_data():
    # আপনার লোকাল নেটওয়ার্কের প্রথম তিনটি সংখ্যা (যেমন: 192.168.0)
    subnet_prefix = '192.168.0'
    devices = scan_network_native(subnet_prefix)
    
    nodes = [{'id': 'router', 'label': 'Gateway Router', 'group': 'router'}]
    edges = []

    for idx, dev in enumerate(devices):
        node_id = f"dev_{idx}"
        nodes.append({
            'id': node_id,
            'label': f"IP: {dev['ip']}",
            'group': 'device'
        })
        edges.append({'from': 'router', 'to': node_id})

    return jsonify({'nodes': nodes, 'edges': edges})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
        
