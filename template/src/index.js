const express = require('express');
const app = express();

const PORT = process.env.APP_PORT || process.env.PORT || 3000;
const APP_NAME = process.env.APP_NAME || 'app';
const COMMIT_SHA = process.env.COMMIT_SHA || 'unknown';

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    app: APP_NAME,
    version: COMMIT_SHA
  });
});

app.get('/', (req, res) => {
  res.json({
    message: `Welcome to ${APP_NAME}!`,
    version: COMMIT_SHA
  });
});

// Error handling
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(500).json({ error: 'Internal Server Error' });
});

app.use((req, res) => {
  res.status(404).json({ error: 'Not Found' });
});

// Start server
const server = app.listen(PORT, () => {
  console.log(`🚀 ${APP_NAME} is running on port ${PORT}`);
  console.log(`📦 Version: ${COMMIT_SHA}`);
  console.log(`🏥 Health check: http://localhost:${PORT}/health`);
});

// Graceful shutdown
const gracefulShutdown = () => {
  console.log('📴 Received shutdown signal, closing server...');
  server.close(() => {
    console.log('✅ Server closed');
    process.exit(0);
  });
};

process.on('SIGTERM', gracefulShutdown);
process.on('SIGINT', gracefulShutdown);
