# NAGP Kubernetes assignment (A Service for Products Data)
    This is an app for Kubernetes : It has a FastAPI Service tier that reads the products records from a PostgreSQL Database tier and it built on GKE

## Links
- Repository: [github.com/shadygoneinsane/k8s-assignment](https://github.com/shadygoneinsane/k8s-assignment)
- Docker Image: [hub.docker.com/r/vikeshkrdass/nagp-products-api](https://hub.docker.com/r/vikeshkrdass/nagp-products-api)
- Live API (records): [http://35.186.254.223/products](http://35.186.254.223/products)
- Screen recording: [Google Drive link](https://drive.google.com/file/d/1lcDQopmg2txxmLEiKy90sEjc4VqnuEcp/view?usp=sharing)


## Requirement Understanding
  The task to build and deploy a two-tier app on Kubernetes. 
  I needed a service API tier and a Database tier.

  - API Service: A small microservice which exposes a HTTP endpoint and it returns records fetched from the database. This must be reached from the outside of the cluster (used Ingress to manage external access to this service ), we can run multiple replicas (for this assignment I have 4), It supports Rolling updates, These recover automatically if any pod dies and these scale while taking load using a HPA

  - Database: A single database which holds one small table (Holds 7 rows). Its reachable only from inside the cluster and the data survives the pod deletion/redeployment.

  - ConfigMap & Secrets : The Database connection settings(host/port/name/user) comes from ConfigMap and is not hardcoded in the image or any pod spec. The database password is stored in Kubernetes Secret file (Not in plain YAML) (db-secret) and is referenced by the deployments via 'secretKeyRef' and it never appears in plaintext in the deployment or ConfigMap. It is a base64-encoded so the secret.yaml is to be treated as sensitive. For a production setup I would not commit the Secret at all as there are better options, examples : Create the secret imperatively and keeping it out of git, Or Use Google Secret Manager with a Operator which adds real encryption, rotation, etc. 

  - Networking: The API Service and the Database talk through Kubernetes Service DNS names and not pod IPs (which when killed would be unreachable if hardcoded). And the API Service is exposed externally via the Ingress.

  - FinOps: The API Service tier defines the CPU and memory requests and the limits. The Deployment Design has the cost-optimization techniques.

## Assumptions

  - Since any tech stack was fine so I have picked FastAPI (Python) for the API tier and PostgreSQL for the database tier.

  - The database runs as a single replica. It uses a ReadWriteOnce volume, which can only attach to one pod at a time, so I went with a Recreate strategy.
    This means there is a few seconds of downtime when the DB pod is replaced, which I assumed is acceptable since the assignment only asks for 1 DB pod with data persistence.

  - The API tier runs 4 replicas as asked in the requirements table, and the HPA(Horizontal Pos Autoscaling) scales it between 4 and 8 pods based on CPU.

  - The products table is initialied once when the database starts for the first time, using an init SQL script mounted from the ConfigMap. On later restarts the data is already on the persistent volume so it does not get seeded again.

  - External access uses the GKE Ingress. I am reaching it through its external IP address.

  - The Docker image is pushed to a public Docker Hub repo so the cluster can pull it without needing registry credentials.


## Solution Overview
  The app has two tiers running in the same Kubernetes cluster.

  Flow of a request:

  User -> Ingress -> api-service -> one of the 4 API pods -> db-service -> Postgres pod -> PVC

  A user hits the Ingress external IP (http://35.186.254.223 for our case). 
  The Ingress forwards to `api-service` which load-balances across the 4 API pods. 
  The API pod that handles the request opens a pooled connection to the database using the `db-service` DNS name and runs a SELECT query on the products table and returns the rows as JSON. 
  The Postgres pod stores its data on a PersistentVolume so the data survives pod restarts.

  API tier: a FastAPI app with three endpoints — `/` (shows which pod answered) 
  `/health` (used by the liveness and readiness probes), and `/products` (returns the records from the database). 
  All DB settings are read from environment variables which come from the ConfigMap and Secret, so nothing is hardcoded. 
  The app keeps a connection pool open instead of opening a new connection per request.

  Database tier: a single PostgreSQL pod. On first boot it runs an init SQL script (mounted from the ConfigMap) that creates the products table and inserts 7 rows. 
  Its data directory is on a PersistentVolumeClaim, so the data is not lost when the pod is deleted or redeployed. 
  The DB is a ClusterIP service so it is only reachable from inside the cluster.

  Kubernetes objects
  - k8s/api-deployment.yaml: Deployment File which runs 4 API pods with rolling updates, probes, resource limits, env from ConfigMap + Secret.
  - k8s/api-service.yaml: Service (ClusterIP) has stable internal address + load-balancing for the API pods.
  - k8s/ingress.yaml: Ingress which exposes the API tier outside the cluster.
  - k8s/hpa.yaml: HorizontalPodAutoscaler(HPA) which scales API pods 4 to 8 on 50% CPU.
  - k8s/db-deployment.yaml: Deployment which runs 1 Postgres pod, has Recreate strategy and mounts PVC + init script.
  - k8s/db-service.yaml: Service (ClusterIP) has internal only DNS name for the database.
  - k8s/pvc.yaml: PersistentVolumeClaim(PVC) has 1Gi disk that keeps the DB data across restarts.
  - k8s/configmap.yaml: ConfigMap has the DB connection settings + the init SQL seed script.
  - k8s/secret.yaml: Secret has the Database password (base64 encoded) and referenced by both deployments.


## Justification for Resources Utilized

  Tried to keep the numbers small but sensible and since the app itself is light. Also wanted to showcase everything while thinking about cost.

  - API CPU and memory (requests and limits per pod - how much compute the pod reserves):
    - requests: 100m CPU and 128Mi memory. This is what each pod is guaranteed as the Scheduler uses it to decide which node has room.
    FastAPI does not need much to just serve JSON so I kept the request low and waste less.
    - limits: 250m CPU and 256Mi memory. This is the ceiling so a single pod can not eat the whole node if something goes wrong. 
    we have a gap between request and limit on purpose so a pod has room to handle a short spike without being throttled straight away.

  - API replicas (4): 
  As the requirement asked for 4. 
  Having more than one pod means the Service keeps serving even if one pod dies and rolling updates can happen without downtime because there is always a healthy pod to take the traffic.

  - Rolling update settings (maxSurge 1, maxUnavailable 0): 
  These are set so that during an update Kubernetes brings up one new pod first and never drops below the 4 running pods.
  So the update happens with zero downtime which is the whole point of having rolling updates.

  - HPA (4 to 8 pods at 50% CPU): 
  It starts at the required 4 and can go up to 8 when it gets busy. 
  We have picked 50% average CPU because if we waited until the pods were near 100% they would already be struggling before new pods came up. 
  50% would scale out a bit early which feels safer.

  - Database replica (1): 
  1 Postgres pod with a ReadWriteOnce volume.
  The assignment only needs a single DB with persistence not a clustered database so one replica is the correct choice here. 
  Running more would not even work cleanly with a ReadWriteOnce disk since it attaches to one pod at a time.

  - PVC size (1Gi): 
  The data is just one small table with 7 rows, so 1Gi is way more than enough. 
  Still wanted a real PersistentVolume though so that we could actually prove the data survives a pod delete.

  - Database resources: 
  We do not put CPU and memory limits on the Postgres pod because the FinOps requirement was written for the API/service tier only. 
  We should have them in a real setup and we should also add requests and limits there as a next step.


## FinOps - Cost Optimization
  The brief asked to find at least three ways to keep Kubernetes costs down. 
  Here are the ones I looked at, and the ones I actually applied.

  1. Right size of the requests and limits using real metrics.
  Instead of guessing, checked the actual usage with the metrics the cluster collects. 
  The HPA showed the API pods sitting at about 2% CPU against the 50% target (`cpu: 2%/50%`)
  so I could confirm the pods were not starved and that my small requests (100m CPU, 128Mi) were already a good fit and not over-reserved. 
  Reserving less per pod means each node fits more pods which means I pay for fewer nodes.

  2. Autoscale instead of running a fixed large number of pods.
  The HPA keeps the API at the required 4 pods when it is quiet and only adds more (up to 8) when CPU actually climbs. 
  So I am not paying for 8 pods around the clock just to handle the occasional busy moment. 
  The extra pods only exist while they are needed and they scale back down after.

  3. Keep the container image small.
  The Dockerfile uses python:3.12-slim instead of the full image and installs deps with --no-cache-dir. 
  The final image is about 60MB. A smaller image means less storage in the registry and faster pulls onto nodes and quicker scale-ups - which all reduce cost.

  4. Modest storage instead of over-provisioning (done).
  The dataset is very tiny thus the PVC is only 1Gi rather than a large default disk. 
  We pay for the disk size asked for and asking for what we need avoids paying for empty space.

  Further opportunities I would do next:
  - Use the cluster autoscaler nodes so that the node pool itself shrinks when pods scale down.
  - Add requests/limits to the Postgres pod too so that the database is also bin-packed efficiently and protected.
  - Use a Vertical Pod Autoscaler in recommendation mode to keep tuning the requests/limits over time from observed usage, instead of setting them once.