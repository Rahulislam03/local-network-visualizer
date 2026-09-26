from flask import Flask, render_template, jsonify, request
import socket
import subprocess
import time
import concurrent.futures

app = Flask(__name__)

COMMON_PORTS = {
    21: 'FTP',
    22: 'SSH',
    23: 'Telnet',
    25: 'SMTP',
    53: 'DNS',
    80: 'HTTP',
    110: 'POP3',
    143: 'IMAP',
    443: 'HTTPS',
    445: 'SMB',
    8080: 'HTTP-Alt',
    5000: 'Flask/HTTP',
    8000: 'HTTP-Dev'
}

def get_current_subnet():
    """অটোমেটিক বর্তমান কানেক্টেড সাবনেট বের করার ব্যাকআপ ফাংশন"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return ".".join(local_ip.split(".")[:3])
    except Exception:
        return "192.168.0"

def grab_banner(ip, port):
    service_name = COMMON_PORTS.get(port, 'Unknown Service')
    banner_info = service_name
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.4)
        sock.connect((ip, port))
        
        if port in [80, 8080, 5000, 8000]:
            sock.sendall(b"HEAD / HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n")
        
        banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
        sock.close()

        if banner:
            for line in banner.splitlines():
                if line.lower().startswith('server:'):
                    server_name = line.split(':', 1)[1].strip()
                    banner_info = f"{service_name} ({server_name})"
                    break
    except Exception:
        pass
        
    return banner_info

def check_single_port(args):
    ip, port = args
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            service = grab_banner(ip, port)
            return {'port': port, 'service': service}
    except Exception:
        pass
    return None

def check_open_ports_and_services(ip):
    open_services = []
    quick_ports = [21, 22, 80, 443, 5000, 8080]
    for port in quick_ports:
        res = check_single_port((ip, port))
        if res:
            open_services.append(f"{res['port']}/{res['service']}")
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
    # ইউজার যদি ম্যানুয়ালি IP বা Subnet পাস করে (যেমন: /api/network-data?subnet=10.0.0)
    manual_subnet = request.args.get('subnet')
    manual_ip = request.args.get('ip')
    
    if manual_subnet:
        subnet_prefix = manual_subnet.strip()
    elif manual_ip:
        # যদি পুরো IP দেন (যেমন: 192.168.1.50) সেখান থেকে Subnet আলাদা করা
        subnet_prefix = ".".join(manual_ip.strip().split(".")[:3])
    else:
        # কিছুই না দিলে স্বয়ংক্রিয়ভাবে কারেন্ট ওয়াইফাই নেটওয়ার্ক স্ক্যান করবে
        subnet_prefix = get_current_subnet()

    gateway_ip = f"{subnet_prefix}.1"
    devices = scan_network_native(subnet_prefix)
    
    nodes = [{
        'id': 'router', 
        'label': f'Gateway Router\n{gateway_ip}', 
        'color': '#38bdf8',
        'shape': 'hexagon',
        'size': 28,
        'ip': gateway_ip
    }]
    edges = []

    for idx, dev in enumerate(devices):
        if dev['ip'] == gateway_ip:
            continue
            
        node_id = f"dev_{idx}"
        services_str = ", ".join(dev['open_services']) if dev['open_services'] else "None"
        
        nodes.append({
            'id': node_id,
            'label': f"{dev['hostname']}\nIP: {dev['ip']}\nPing: {dev['latency']} ms\nServices: {services_str}",
            'color': '#f59e0b',
            'shape': 'dot',
            'size': 20,
            'ip': dev['ip']
        })
        edges.append({'from': 'router', 'to': node_id})

    return jsonify({
        'total_devices': len(devices),
        'nodes': nodes, 
        'edges': edges
    })

@app.route('/api/scan-ports/<ip>')
def scan_device_ports(ip):
    open_ports = []
    ports_to_scan = [(ip, p) for p in range(1, 1025)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        results = executor.map(check_single_port, ports_to_scan)
        for res in results:
            if res:
                open_ports.append(res)
                
    return jsonify({'ip': ip, 'open_ports': open_ports})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
