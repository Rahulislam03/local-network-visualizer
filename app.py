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

def detect_active_local_ip():
    """
    মেশিনের একটিভ লোকাল IP এবং সাবনেট প্রিফিক্স স্বয়ংক্রিয়ভাবে খুঁজে বের করে।
    এটি macOS এর routing table ব্যবহার করে সঠিক ইন্টারফেস থেকে IP নির্ণয় করে।
    """
    # পদ্ধতি ১: সকেট কানেকশন ট্রাই করা
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        if not local_ip.startswith("127."):
            subnet = ".".join(local_ip.split(".")[:3])
            print(f"[+] Auto Detected IP: {local_ip} | Subnet: {subnet}")
            return local_ip, subnet
    except Exception:
        pass

    # পদ্ধতি ২: macOS `ifconfig` কমান্ড চালিয়ে IP খোঁজা (Fallback)
    try:
        cmd = "ifconfig | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}'"
        output = subprocess.check_output(cmd, shell=True).decode('utf-8').strip().splitlines()
        for ip in output:
            if ip and not ip.startswith("127."):
                subnet = ".".join(ip.split(".")[:3])
                print(f"[+] Fallback Detected IP: {ip} | Subnet: {subnet}")
                return ip, subnet
    except Exception:
        pass

    # ব্যাকআপ ডিফল্ট
    return "192.168.0.100", "192.168.0"

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
    manual_subnet = request.args.get('subnet')
    
    # প্রথমে অটোমেটিক আইপি ও সাবনেট খুঁজে বের করবে
    auto_ip, auto_subnet = detect_active_local_ip()

    if manual_subnet and manual_subnet.strip():
        val = manual_subnet.strip()
        # যদি ইউজার পুরো IP লিখে পাঠায় (যেমন: 192.168.68.54)
        if val.count('.') == 3:
            subnet_prefix = ".".join(val.split(".")[:3])
        else:
            subnet_prefix = val
    else:
        # ইনপুট ফাঁকা থাকলে অটো-ডিটেক্ট করা সাবনেট ব্যবহার করবে
        subnet_prefix = auto_subnet

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
        'detected_ip': auto_ip,
        'scanned_subnet': subnet_prefix,
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
    # অ্যাপ স্টার্ট হলেই প্রথমে IP ও Subnet টার্মিনালে প্রিন্ট করবে
    my_ip, my_subnet = detect_active_local_ip()
    print("="*50)
    print(f" Your Active Local IP : {my_ip}")
    print(f" Auto Scanning Subnet: {my_subnet}.1 to {my_subnet}.254")
    print("="*50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
