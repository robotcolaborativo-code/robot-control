# config.py - Configuración de la base de datos
import os

def get_mysql_config():
    """Obtiene configuración MySQL desde variables de entorno de Railway"""
    
    # USAR DATABASE_URL en lugar de MYSQL_URL
    mysql_url = os.environ.get('DATABASE_URL') or os.environ.get('MYSQL_URL')
    
    if mysql_url:
        # Extraer datos de la URL automáticamente
        try:
            # Formato: mysql://root:password@host:port/railway
            mysql_url = mysql_url.replace('mysql://', '')
            user_pass, host_db = mysql_url.split('@')
            user, password = user_pass.split(':')
            host_port, database = host_db.split('/')
            host, port = host_port.split(':') if ':' in host_port else (host_port, '3306')
            
            return {
                'host': host,
                'port': int(port),
                'user': user,
                'password': password,
                'database': database
            }
        except Exception as e:
            print(f"❌ Error parseando DATABASE_URL: {e}")
            print(f"URL recibida: {mysql_url}")
    
    # Fallback: usar configuración manual (SOLO PARA PRUEBAS)
    return {
        'host': 'turntable.proxy.rlwy.net',
        'user': 'root',
        'password': 'QttFmgSWJcoJTFKJNFwuschPWPSESxWs',
        'database': 'railway', 
        'port': 57488
    }
