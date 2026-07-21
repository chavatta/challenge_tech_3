import os
import logging
from flask import Flask, request, jsonify
from kubernetes import client, config
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Kubernetes client
try:
    config.load_incluster_config()
    apps_v1 = client.AppsV1Api()
    log.info("Kubernetes in-cluster config loaded successfully.")
except Exception as e:
    log.warning(f"Failed to load in-cluster config (running locally?): {e}")
    try:
        config.load_kube_config()
        apps_v1 = client.AppsV1Api()
        log.info("Kubernetes local kubeconfig loaded successfully.")
    except Exception as ex:
        log.error(f"Failed to load local kubeconfig: {ex}")
        apps_v1 = None

def restart_deployment(namespace, deployment_name):
    if not apps_v1:
        log.error("Kubernetes client is not initialized.")
        return False
    try:
        log.info(f"Triggering rollout restart for deployment/{deployment_name} in namespace {namespace}...")
        # Get the current deployment object
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        
        # Initialize annotations if they don't exist
        if not deployment.spec.template.metadata.annotations:
            deployment.spec.template.metadata.annotations = {}
        
        # Add or update the restart annotation with the current UTC time
        deployment.spec.template.metadata.annotations['kubectl.kubernetes.io/restartedAt'] = datetime.datetime.utcnow().isoformat()
        
        # Patch the deployment
        apps_v1.patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=deployment)
        log.info(f"Rollout restart patch successfully applied to deployment/{deployment_name}.")
        return True
    except Exception as e:
        log.error(f"Failed to patch deployment/{deployment_name} in namespace {namespace}: {e}")
        return False

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint called by Alertmanager when alerts fire."""
    data = request.get_json()
    if not data:
        log.warning("Received empty webhook payload")
        return jsonify({"error": "empty payload"}), 400
    
    log.info(f"Webhook received payload: {data}")
    
    status = data.get('status', 'firing')
    alerts = data.get('alerts', [])
    
    # If the alert is firing, inspect it
    if status == 'firing':
        for alert in alerts:
            labels = alert.get('labels', {})
            alert_name = labels.get('alertname', 'Unknown')
            # Look for service label or alertname specific to auth-service
            service_name = labels.get('service', 'auth-service')
            
            log.info(f"Handling firing alert: {alert_name} for service: {service_name}")
            
            # Trigger Self-Healing action for auth-service
            if service_name == 'auth-service' or 'auth' in alert_name.lower():
                success = restart_deployment("togglemaster", "auth-service")
                if success:
                    return jsonify({"status": "self-healing triggered", "deployment": "auth-service"}), 200
                else:
                    return jsonify({"status": "error", "message": "self-healing failed"}), 500
                
    return jsonify({"status": "no self-healing action taken"}), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
