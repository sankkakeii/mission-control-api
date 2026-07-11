module.exports = {
  apps: [
    {
      name: "mission-control-api",
      script: "./start.sh",
      interpreter: "bash",
      cwd: "/root/node-pocket/mission-control-api",
      env: {
        NODE_ENV: "production",
        LLM_BACKEND: "openrouter",
        LIVE_MODE: "true",
      },
      max_memory_restart: "512M",
      autorestart: true,
      watch: false,
      exp_backoff_restart_delay: 100,
      max_restarts: 10,
      restart_delay: 5000,
      error_file: "/root/.pm2/logs/mission-control-api-error.log",
      out_file: "/root/.pm2/logs/mission-control-api-out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,
    },
  ],
};
