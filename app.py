from flask import Flask, render_template, jsonify
import socket
import subprocess
import time
import concurrent.futures

app = Flask(__name__)

COMMON_PORTS = [22, 80, 443, 8080]

def check_open_ports(ip):
    open_ports = []
    for port in COMMON_PORTS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.3)
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(port)
            sock.close()
        except Exception:
            pass
    return open_ports

def ping_and_inspect(ip):
    try:
        start_time = time.time()
        output = subprocess.run(['ping', '-c', '1', '-w', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        latency = round((time.time() - start_time) * 1000, 2)
        
        if output.returncode == 0:
            # Hostname পাওয়ার চেষ্টা
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except Exception:
                hostname = "Unknown Device"

            # ওপেন পোর্ট চেক
            open_ports = check_open_ports(ip)
            
            return {
                'ip': ip, 
                'latency': latency, 
                'hostname': hostname,
                'open_ports': open_ports
            }
    except Exception:
        pass
    return None

def scan_network_native(subnet_prefix):
    devices = []
    ip_list = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(ping_and_inspect, ip_list)
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
    
    nodes = [{
        'id': 'router', 
        'label': 'Gateway Router\n192.168.0.1', 
        'color': '#3b82f6',
        'shape': 'hexagon',
        'size': 30
    }]
    edges = []

    for idx, dev in enumerate(devices):
        if dev['ip'] == f"{subnet_prefix}.1":
            continue
            
        node_id = f"dev_{idx}"
        ports_str = ", ".join(map(str, dev['open_ports'])) if dev['open_ports'] else "None"
        
        nodes.append({
            'id': node_id,
            'label': f"{dev['hostname']}\nIP: {dev['ip']}\nPing: {dev['latency']} ms\nPorts: {ports_str}",
            'color': '#f59e0b',
            'shape': 'dot',
            'size': 20
        })
        edges.append({'from': 'router', 'to': node_id})

    return jsonify({
        'total_devices': len(devices),
        'nodes': nodes, 
        'edges': edges
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    
