package main

import (
	"log"
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
)

// HealthResponse represents the health check response
type HealthResponse struct {
	Status    string  `json:"status"`
	Version   string  `json:"version"`
	CommitSHA *string `json:"commit_sha,omitempty"`
	Timestamp string  `json:"timestamp"`
}

// MessageResponse represents a simple message response
type MessageResponse struct {
	Message   string `json:"message"`
	Timestamp string `json:"timestamp"`
}

// StatusResponse represents the API status response
type StatusResponse struct {
	API         string `json:"api"`
	Version     string `json:"version"`
	Environment string `json:"environment"`
	Port        string `json:"port"`
}

func main() {
	// Load environment variables from .env file if it exists
	_ = godotenv.Load()

	// Set Gin mode based on environment
	if os.Getenv("ENVIRONMENT") == "production" {
		gin.SetMode(gin.ReleaseMode)
	}

	// Create Gin router
	r := gin.Default()

	// Add middleware for CORS and logging
	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	})

	// Health check endpoint
	r.GET("/health", func(c *gin.Context) {
		commitSHA := os.Getenv("COMMIT_SHA")
		response := HealthResponse{
			Status:    "healthy",
			Version:   "1.0.0",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		}
		if commitSHA != "" {
			response.CommitSHA = &commitSHA
		}
		c.JSON(http.StatusOK, response)
	})

	// Root endpoint
	r.GET("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, MessageResponse{
			Message:   "Hello from Go/Gin!",
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		})
	})

	// API status endpoint
	r.GET("/api/status", func(c *gin.Context) {
		port := os.Getenv("APP_PORT")
		if port == "" {
			port = os.Getenv("PORT")
		}
		if port == "" {
			port = "3000"
		}

		environment := os.Getenv("ENVIRONMENT")
		if environment == "" {
			environment = "development"
		}

		c.JSON(http.StatusOK, StatusResponse{
			API:         "running",
			Version:     "1.0.0",
			Environment: environment,
			Port:        port,
		})
	})

	// Start server
	port := os.Getenv("APP_PORT")
	if port == "" {
		port = os.Getenv("PORT")
	}
	if port == "" {
		port = "3000"
	}

	log.Printf("Starting server on port %s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatal("Failed to start server:", err)
	}
}

