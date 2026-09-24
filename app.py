from flask import Flask, render_template, jsonify
import socket
import subprocess
import time
import concurrent.futures

app = Flask(__name__)

# কমন কিছু সিকিউরিটি ও সার্ভিস পোর্ট
COMMON_PORTS = {
    21: 'FTP',
    22: 'SSH',
    80: 'HTTP',
    443: 'HTTPS',
    8080: 'HTTP-Alt',
    5000: 'Flask/HTTP',
    8000: 'HTTP-Dev'
}

def grab_banner(ip, port):
    """ওপেন পোর্টের ব্যানার ও সার্ভিস নাম বের করার ফাংশন"""
    service_name = COMMON_PORTS.get(port, 'Unknown')
    banner_info = service_name
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect((ip, port))
        
        # HTTP পোর্টের জন্য রিকোয়েস্ট পাঠিয়ে ব্যানার নেওয়া
        if port in [80, 8080, 5000, 8000]:
            sock.sendall(b"HEAD / HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n")
        
        banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        sock.close()

        # সার্ভার হেডার থেকে সার্ভিস চেনা
        if banner:
            for line in banner.splitlines():
                if line.lower().startswith('server:'):
                    server_name = line.split(':', 1)[1].strip()
                    banner_info = f"{service_name} ({server_name})"
                    break
    except Exception:
        pass
        
    return f"{port}/{banner_info}"

def check_open_ports_and_services(ip):
    open_services = []
    for port in COMMON_PORTS.keys():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                service_details = grab_banner(ip, port)
                open_services.append(service_details)
        except Exception:
            pass
    return open_services

def get_device_name(ip):
    try:
        if ip == '127.0.0.1' or ip == socket.gethostbyname(socket.gethostname()):
            return f"This Device ({socket.gethostname()})"
    except Exception:
        pass
        
    try:
        host = socket.gethostbyaddr(ip)[0]
        return host.split('.')[0]
    except Exception:
        pass

    return "Mobile / Smart Device"

def ping_and_inspect(ip):
    try:
        start_time = time.time()
        output = subprocess.run(['ping', '-c', '1', '-w', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        latency = round((time.time() - start_time) * 1000, 2)
        
        if output.returncode == 0:
            dev_name = get_device_name(ip)
            open_services = check_open_ports_and_services(ip)
            
            return {
                'ip': ip, 
                'latency': latency, 
                'hostname': dev_name,
                'open_services': open_services
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
        'color': '#38bdf8',
        'shape': 'hexagon',
        'size': 28
    }]
    edges = []

    for idx, dev in enumerate(devices):
        if dev['ip'] == f"{subnet_prefix}.1":
            continue
            
        node_id = f"dev_{idx}"
        services_str = ", ".join(dev['open_services']) if dev['open_services'] else "None"
        
        nodes.append({
            'id': node_id,
            'label': f"{dev['hostname']}\nIP: {dev['ip']}\nPing: {dev['latency']} ms\nServices: {services_str}",
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
                    
