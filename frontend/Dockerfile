FROM node:20-alpine

WORKDIR /app

# npm ci uses the lockfile for reproducible installs; it requires
# package-lock.json to be present, which COPY package*.json guarantees.
COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3000
# -H 0.0.0.0 so the dev server is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
