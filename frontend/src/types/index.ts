// ============================================================
// types/index.ts
// Mirrors the Pydantic schemas from backend/app/schemas/models.py
// ============================================================

// ── Enums ─────────────────────────────────────────────────────
export type PredictionLabel = "NORMAL" | "ATTACK";
export type SeverityLevel   = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

// ── Network Flow Features ─────────────────────────────────────
export interface NetworkFlowFeatures {
  duration:                    number;
  protocol_type:               string;
  service:                     string;
  flag:                        string;
  src_bytes:                   number;
  dst_bytes:                   number;
  land:                        number;
  wrong_fragment:              number;
  urgent:                      number;
  hot:                         number;
  num_failed_logins:           number;
  logged_in:                   number;
  num_compromised:             number;
  root_shell:                  number;
  num_root:                    number;
  num_file_creations:          number;
  num_shells:                  number;
  num_access_files:            number;
  is_guest_login:              number;
  count:                       number;
  srv_count:                   number;
  serror_rate:                 number;
  srv_serror_rate:             number;
  rerror_rate:                 number;
  srv_rerror_rate:             number;
  same_srv_rate:               number;
  diff_srv_rate:               number;
  srv_diff_host_rate:          number;
  dst_host_count:              number;
  dst_host_srv_count:          number;
  dst_host_same_srv_rate:      number;
  dst_host_diff_srv_rate:      number;
  dst_host_same_src_port_rate: number;
  dst_host_srv_diff_host_rate: number;
  dst_host_serror_rate:        number;
  dst_host_srv_serror_rate:    number;
  dst_host_rerror_rate:        number;
  dst_host_srv_rerror_rate:    number;
}

// ── Prediction ────────────────────────────────────────────────
export interface PredictionResult {
  prediction_id: string;
  label:         PredictionLabel;
  probability:   number;
  severity:      SeverityLevel;
  threshold:     number;
  is_anomaly:    boolean;
  timestamp:     string;
  inference_ms:  number;
}

export interface PredictionRequest {
  features:  NetworkFlowFeatures;
  threshold: number;
}

export interface BatchPredictionResponse {
  total:          number;
  anomaly_count:  number;
  normal_count:   number;
  results:        PredictionResult[];
  processing_ms:  number;
  summary:        Record<string, unknown>;
}

// ── Upload ────────────────────────────────────────────────────
export interface UploadResponse {
  upload_id:      string;
  filename:       string;
  file_type:      string;
  rows_processed: number;
  anomaly_count:  number;
  normal_count:   number;
  anomaly_rate:   number;
  results:        PredictionResult[];
  report_id:      string | null;
  processing_ms:  number;
  timestamp:      string;
}

// ── Chat ──────────────────────────────────────────────────────
export interface ChatMessage {
  role:    "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  question:            string;
  history:             ChatMessage[];
  prediction_context?: PredictionResult;
}

export interface ChatResponse {
  answer:      string;
  sources:     string[];
  model_used:  string;
  response_ms: number;
  timestamp:   string;
}

// ── Health ────────────────────────────────────────────────────
export interface HealthResponse {
  status:    "ok" | "degraded" | "unavailable";
  app_name:  string;
  version:   string;
  timestamp: string;
  services:  Record<string, string>;
}

// ── Model Info ────────────────────────────────────────────────
export interface ModelInfoResponse {
  architecture:      string;
  num_features:      number;
  hidden_size:       number;
  num_layers:        number;
  total_params:      number;
  trainable_params:  number;
  checkpoint_path:   string;
  device:            string;
  anomaly_threshold: number;
  dataset:           string;
}

// ── Reports ───────────────────────────────────────────────────
export interface ReportSummary {
  report_id:     string;
  filename:      string;
  created_at:    string;
  total_flows:   number;
  anomaly_count: number;
  anomaly_rate:  number;
}

// ── RAG Stats ─────────────────────────────────────────────────
export interface RAGStats {
  status:          string;
  collection_name: string;
  total_chunks:    number;
  embed_model:     string;
  llm_model:       string;
  kb_path:         string;
  db_path:         string;
}

// ── WebSocket ─────────────────────────────────────────────────
export interface WSMessage {
  event:     "prediction" | "error" | "pong" | "connected" | "summary";
  payload:   Record<string, unknown>;
  timestamp: string;
}

// ── Dashboard ─────────────────────────────────────────────────
export interface TrafficDataPoint {
  time:     string;
  normal:   number;
  attack:   number;
  total:    number;
}

export interface DashboardStats {
  totalAnalysed:  number;
  anomalyCount:   number;
  normalCount:    number;
  anomalyRate:    number;
  avgProbability: number;
  lastUpdated:    string;
}
