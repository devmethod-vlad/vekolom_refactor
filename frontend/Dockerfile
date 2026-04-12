ARG NODE_VERSION=22-bookworm

FROM node:${NODE_VERSION}
WORKDIR /frontend

COPY package.json ./
# лучше COPY package*.json ./ если будет lock-файл
RUN npm install

COPY ./ ./