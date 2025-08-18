const express = require('express');
const app = express();

const PORT = process.env.PORT || 3000;
const APP_NAME = process.env.APP_NAME || 'app';
const COMMIT_SHA = process.env.COMMIT_SHA || 'unknown';

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check endpoint (required)
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    app: APP_NAME,
    version: COMMIT_SHA,
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: `Welcome to ${APP_NAME}!`,
    version: COMMIT_SHA,
    endpoints: {
      health: '/health',
      info: '/info'
    }
  });
});

// Info endpoint
app.get('/info', (req, res) => {
  res.json({
    app: APP_NAME,
    version: COMMIT_SHA,
    node: process.version,
    env: process.env.NODE_ENV || 'development',
    memory: process.memoryUsage(),
    uptime: process.uptime()
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Error:', err);
  res.status(err.status || 500).json({
    error: {
      message: err.message || 'Internal Server Error',
      ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
    }
  });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    error: {
      message: 'Not Found',
      path: req.path
    }
  });
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
