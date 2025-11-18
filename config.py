# config.py - Configuración de la base de datoss
import os

def get_mysql_config():
    """Obtiene configuración MySQL desde variables de entorno de Railway"""
    
    # Railway provee MYSQL_URL en formato: mysql://usuario:contraseña@host:puerto/base_datos
    mysql_url = os.environ.get('MYSQL_URL')
    
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
            print(f"❌ Error parseando MYSQL_URL: {e}")
    
    # Fallback: usar configuración manual
    return {
        'host': 'TU_HOST_AQUI',  # <-- Railway lo provee automáticamente
        'user': 'root',
        'password': 'QttFmgSWJcoJTFKJNFwuschPWPSESxWs',
        'database': 'railway',
        'port': 3306
    }
