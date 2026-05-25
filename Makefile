include .env

.PHONY: all build auth evaluation analytics flag targeting push clean
.SILENT: auth evaluation analytics flag targeting push clean help

all: clean build push
	
build: auth evaluation analytics flag targeting

auth:
	docker build --tag=auth-service:v1 ./auth-service/
	docker tag auth-service:v1 ${AWS_AUTH_SERVICE_ECR}auth-service:v1

evaluation:
	docker build --tag=evaluation-service:v1 ./evaluation-service/
	docker tag evaluation-service:v1 ${AWS_EVALUATION_SERVICE_ECR}evaluation-service:v1

analytics:
	docker build --tag=analytics-service:v1 ./analytics-service/
	docker tag analytics-service:v1 ${AWS_ANALYTICS_SERVICE_ECR}analytics-service:v1

flag:
	docker build --tag=flag-service:v1 ./flag-service/
	docker tag flag-service:v1 ${AWS_FLAG_SERVICE_ECR}flag-service:v1

targeting:
	docker build --tag=targeting-service:v1 ./targeting-service/
	docker tag targeting-service:v1 ${AWS_TARGETING_SERVICE_ECR}targeting-service:v1

aws:
	@echo "Execute: aws ecr get-login-password --region <regiao> | docker login --username AWS --password-stdin <account>.dkr.ecr.<regiao>.amazonaws.com"

push: aws
	docker push ${AWS_AUTH_SERVICE_ECR}auth-service:v1
	docker push ${AWS_EVALUATION_SERVICE_ECR}evaluation-service:v1
	docker push ${AWS_ANALYTICS_SERVICE_ECR}analytics-service:v1
	docker push ${AWS_FLAG_SERVICE_ECR}flag-service:v1
	docker push ${AWS_TARGETING_SERVICE_ECR}targeting-service:v1

clean:
	docker rmi -f auth-service:v1 2> /dev/null
	docker rmi -f ${AWS_AUTH_SERVICE_ECR}auth-service:v1 2> /dev/null
	docker rmi -f evaluation-service:v1 2> /dev/null
	docker rmi -f ${AWS_EVALUATION_SERVICE_ECR}evaluation-service:v1 2> /dev/null
	docker rmi -f analytics-service:v1 2> /dev/null
	docker rmi -f ${AWS_ANALYTICS_SERVICE_ECR}analytics-service:v1 2> /dev/null
	docker rmi -f flag-service:v1 2> /dev/null
	docker rmi -f ${AWS_FLAG_SERVICE_ECR}flag-service:v1 2> /dev/null
	docker rmi -f targeting-service:v1 2> /dev/null
	docker rmi -f ${AWS_TARGETING_SERVICE_ECR}targeting-service:v1 2> /dev/null
	
help:
	echo "Available targets:"
	echo "    all (default) 	- Follow the default process to build all the contanier images and send them to the private AWS ECR registry"
	echo "    build         	- Build all the contanier images"
	echo "    auth    			- Build only the auth contanier image"
	echo "    evaluation  		- Build only the evaluation contanier image"
	echo "    analytics   		- Build only the analytics contanier image"
	echo "    flag      		- Build only the flag contanier image"
	echo "    targeting   		- Build only the targeting contanier image"
	echo "    aws         		- Login to AWS Cloud using AWS CLI"
	echo "    push         		- Send all the container images to the private AWS ECR registry"
	echo "    clean      		- Remove all the images generated in the make process"

# CI trigger: shared file change forces all microservice workflows to rebuild
