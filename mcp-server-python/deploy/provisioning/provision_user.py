"""
Provisioning script for per-user Memory Bank Cloud Run services.
Requires: google-cloud-run

Install: pip install google-cloud-run
Usage: python provision_user.py --project PROJECT --user-id USER ...
"""
import argparse
from google.cloud import run_v2
from google.api_core.exceptions import NotFound

def deploy_user_service(project_id: str, region: str, user_id: str, image: str, service_account: str, engine_name: str, bearer_token: str):
    """Deploys a new Cloud Run service for a specific user."""
    
    # Sanitize user_id for service name (must be lowercase, hyphens)
    service_name = f"openreflect-{user_id.lower().replace('_', '-')}"
    parent = f"projects/{project_id}/locations/{region}"
    service_id = f"{parent}/services/{service_name}"
    
    client = run_v2.ServicesClient()
    
    # Define the container
    container = run_v2.Container()
    container.image = image
    container.ports = [run_v2.ContainerPort(container_port=8080)]
    container.resources.limits = {"cpu": "1000m", "memory": "1Gi"}
    
    env_vars = [
        {"name": "GOOGLE_CLOUD_PROJECT", "value": project_id},
        {"name": "GOOGLE_CLOUD_LOCATION", "value": region},
        {"name": "AGENT_ENGINE_NAME", "value": engine_name},
        {"name": "CONNECTOR_BEARER_TOKEN", "value": bearer_token}
    ]
    container.env = [run_v2.EnvVar(name=e["name"], value=e["value"]) for e in env_vars]

    # Define the service
    service = run_v2.Service()
    service.template.containers = [container]
    service.template.service_account = service_account
    service.template.scaling.max_instance_count = 1
    
    # Check if exists
    try:
        print(f"Checking if service {service_name} exists...")
        client.get_service(name=service_id)
        print(f"Service {service_name} already exists. Updating...")
        
        # When updating, we must use the service name in the object
        service.name = service_id
        operation = client.update_service(service=service)
    except NotFound:
        print(f"Creating new service {service_name}...")
        request = run_v2.CreateServiceRequest(
            parent=parent,
            service=service,
            service_id=service_name
        )
        operation = client.create_service(request=request)
        
    print("Waiting for operation to complete...")
    response = operation.result()
    print(f"Service deployed successfully: {response.uri}")
    return response.uri

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision Memory Bank Service")
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--engine-name", required=True)
    parser.add_argument("--token", required=True)
    
    args = parser.parse_args()
    
    deploy_user_service(
        args.project, args.region, args.user_id, 
        args.image, args.service_account, 
        args.engine_name, args.token
    )
