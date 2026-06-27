import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
}

api.interceptors.request.use((config) => {
  const csrfToken = getCookie("csrftoken");
  if (csrfToken && config.method && config.method.toUpperCase() !== "GET") {
    config.headers["X-CSRFToken"] = csrfToken;
  }
  return config;
});

export interface Organization {
  id: string;
  name: string;
  legal_name: string;
  inn: string;
  kpp: string;
  is_active: boolean;
  is_test: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppUser {
  id: number;
  username: string;
  password?: string;
  plaintext_password: string;
  is_staff: boolean;
  is_active: boolean;
  organization: string | null;
  organization_name: string | null;
  is_test_client: boolean;
  date_joined: string;
  last_login: string | null;
}

export interface ImportBatch {
  id: string;
  organization: string;
  organization_name: string;
  data_type: string;
  status: string;
  original_filename: string;
  sha256: string;
  file_size: number;
  period_start: string | null;
  period_end: string | null;
  row_count: number;
  amount_total: string | null;
  error_message: string;
  warnings: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TimelineRow {
  period: string;
  gross_sales_total: number;
  returns_total: number;
  amount_total: number;
  quantity_total: number;
  documents_count: number;
}

export interface ProductRow {
  nomenclature: string | null;
  display_name: string | null;
  gross_sales_total: number;
  returns_total: number;
  amount_total: number;
  quantity_total: number;
  gross_quantity_total: number;
  returns_quantity_total: number;
  average_price: number | null;
  share_of_total: number | null;
  returns_share: number | null;
}

export interface CounterpartyRow {
  key: string | null;
  gross_sales_total: number;
  returns_total: number;
  amount_total: number;
  quantity_total: number;
  gross_quantity_total: number;
  returns_quantity_total: number;
  documents_count: number;
  share_of_total: number | null;
  returns_share: number | null;
}

export interface SalesVsPaymentsRow {
  organization_id: string;
  legal_entity: string | null;
  contract_number: string | null;
  sales_total: number;
  payments_total: number;
  difference: number;
  payment_share: number | null;
}

export interface CashFlowActualRow {
  date: string;
  inflow: number;
  outflow: number;
  net_cash_flow: number;
}

export interface CashFlowForecastRow {
  date: string;
  predicted_inflow: number;
  predicted_outflow: number;
  predicted_net_cash_flow: number;
}

export interface CashFlowResponse {
  horizon_days: number;
  actual: CashFlowActualRow[];
  forecast: CashFlowForecastRow[];
}
