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
  created_at: string;
  updated_at: string;
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
  gross_sales_total: number;
  returns_total: number;
  amount_total: number;
  quantity_total: number;
  average_price: number | null;
  share_of_total: number | null;
}

export interface CounterpartyRow {
  key: string | null;
  gross_sales_total: number;
  returns_total: number;
  amount_total: number;
  quantity_total: number;
  documents_count: number;
  share_of_total: number | null;
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
