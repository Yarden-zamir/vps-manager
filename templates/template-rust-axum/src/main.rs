use axum::{extract::State, http::StatusCode, response::IntoResponse, routing::get, Json, Router};
use chrono::Utc;
use serde::Serialize;
use std::{env, net::SocketAddr, sync::Arc};
use tokio::net::TcpListener;

#[derive(Clone)]
struct AppState {
    app_name: String,
    commit_sha: String,
}

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    app: String,
    version: String,
}

#[derive(Serialize)]
struct MessageResponse {
    message: String,
    timestamp: String,
}

#[tokio::main]
async fn main() {
    let port = env::var("APP_PORT")
        .or_else(|_| env::var("PORT"))
        .unwrap_or_else(|_| "3000".to_string())
        .parse::<u16>()
        .expect("APP_PORT must be a valid TCP port");

    let state = Arc::new(AppState {
        app_name: env::var("APP_NAME").unwrap_or_else(|_| "app-template".to_string()),
        commit_sha: env::var("COMMIT_SHA").unwrap_or_else(|_| "unknown".to_string()),
    });

    let app = Router::new()
        .route("/", get(root))
        .route("/health", get(health))
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let listener = TcpListener::bind(addr).await.expect("failed to bind server");
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("server failed");
}

async fn root(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    Json(MessageResponse {
        message: format!("Welcome to {}!", state.app_name),
        timestamp: Utc::now().to_rfc3339(),
    })
}

async fn health(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    (
        StatusCode::OK,
        Json(HealthResponse {
            status: "healthy",
            app: state.app_name.clone(),
            version: state.commit_sha.clone(),
        }),
    )
}

async fn shutdown_signal() {
    let _ = tokio::signal::ctrl_c().await;
}
