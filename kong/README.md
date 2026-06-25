# Kong

Basic Kong installation that renders full manifests with defaults.


## Create installer
```sh
helm repo add kong https://charts.konghq.com
helm repo update

# render manifests
helm show crds kong/ingress > crd.yaml
helm template kong kong/ingress \
  -n kong \
  --create-namespace \
  > kong.yaml
```

## Install Kong Ingress Controller

Install kong in kubernetes cluster:
```sh
kubectl create ns kong
kubectl apply -f crd.yaml
kubectl apply -f kong.yaml
```
