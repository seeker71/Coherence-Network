export type EndpointTraceabilityItem = {
  path: string;
  methods: string[];
  traceability?: {
    fully_traced?: boolean;
    gaps?: string[];
  };
  usage?: {
    event_count?: number;
  };
  web_link?: {
    tracked?: boolean;
    explicit_count?: number;
    catalog_route?: string;
    evidence?: Array<{
      source_file?: string;
      line?: number | null;
      web_route?: string | null;
      evidence_type?: string;
    }>;
  };
};

export type TraceabilityResponse = {
  summary?: {
    total_endpoints?: number;
    fully_traced?: number;
    with_usage_events?: number;
    with_web_link?: number;
    with_explicit_web_link?: number;
    missing_web_link?: number;
    missing_idea?: number;
    missing_spec?: number;
    missing_process?: number;
    missing_validation?: number;
  };
  items?: EndpointTraceabilityItem[];
};

export type CanonicalRoutesResponse = {
  api_routes?: Array<{
    path?: string;
    methods?: string[];
  }>;
};

export type ProbeResult = {
  path: string;
  method: string;
  status: "pass" | "fail" | "skipped";
  httpStatus?: number;
  error?: string;
  durationMs?: number;
  url?: string;
};

export type JsonResult<T> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
};
