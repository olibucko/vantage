export interface Service {
  port: number;
  name: string;
  banner?: string | null;
}

export interface NetworkNode {
  ip: string;
  mac: string;
  hostname: string;
  vendor: string;
  os: string;
  type: string;
  ports: number[];
  services?: Service[];
  deviceName?: string | null;
  confidence?: number;
  lastSeen?: number;
}

export interface GraphNode extends NetworkNode {
  id: string;
  name: string;
  val: number;
  color: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface GraphLink {
  source: string;
  target: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}
