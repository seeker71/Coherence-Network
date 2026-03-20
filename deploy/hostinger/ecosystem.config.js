// PM2 Ecosystem — Coherence Network (Hostinger VPS)
module.exports = {
  apps: [
    {
      name: "coherence-api",
      cwd: "/opt/coherence/api",
      interpreter: "/opt/coherence/api/.venv/bin/python",
      script: "-m",
      args: "uvicorn app.main:app --host 127.0.0.1 --port 8000",
      env: {
        PORT: 8000,
      },
      max_memory_restart: "512M",
      autorestart: true,
      watch: false,
    },
    {
      name: "coherence-web",
      cwd: "/opt/coherence/web",
      script: "server.js",
      env: {
        PORT: 3000,
        NODE_ENV: "production",
        HOSTNAME: "127.0.0.1",
      },
      max_memory_restart: "512M",
      autorestart: true,
      watch: false,
    },
  ],
};
