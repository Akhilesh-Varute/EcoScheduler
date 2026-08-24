export type Role = "admin" | "developer" | "finance";

export interface User {
  userId: string;
  email: string;
  role: Role;
  awsAccounts: string[];
  name?: string;
  createdAt: number;
  updatedAt: number;
}

export interface LoginResponse {
  success: true;
  message: string;
  token: string;
  user: User;
}

export interface Schedule {
  scheduleId: string;
  userId: string;
  name: string;
  accountId: string;
  instanceIds: string[];
  startCron: string;
  stopCron: string;
  timezone: string;
  exceptions: string[];
  tags: Record<string, string>;
  enabled: boolean;
  dryRun: boolean;
  createdAt: number;
  updatedAt: number;
  lastStartTime?: string;
  lastStopTime?: string;
  lastAction?: string;
  lastActionResult?: string;
  lastError?: string;
  startRuleArn?: string;
  stopRuleArn?: string;
}

export interface SchedulesListResponse {
  success: true;
  schedules: Schedule[];
  count: number;
  nextToken: string | null;
}

export interface ScheduleInput {
  name: string;
  accountId: string;
  instanceIds: string[];
  startCron: string;
  stopCron: string;
  timezone?: string;
  dryRun?: boolean;
}

export interface Ec2Instance {
  instanceId: string;
  name: string;
  instanceType: string;
  state: string;
  privateIpAddress: string | null;
  publicIpAddress: string | null;
  launchTime: string | null;
  tags: Record<string, string>;
  securityGroups: string[];
  vpcId: string | null;
  subnetId: string | null;
  platform: string;
}

export interface Ec2ListResponse {
  success: true;
  instances: Ec2Instance[];
  count: number;
}

export interface AccountVerifyResponse {
  success: true;
  connected: true;
  instanceCount: number;
}

export interface RefreshTokenResponse {
  success: true;
  message: string;
  token: string;
  user: User;
}

export interface SavingsSummaryReport {
  type: "summary";
  startDate: string;
  endDate: string;
  totalHoursSaved: number;
  totalCostSaved: number;
  instanceCount: number;
  filters: { accountId: string | null; userId: string | null };
}

export interface SavingsScheduleReport {
  type: "schedule";
  scheduleId: string;
  scheduleName: string;
  startDate: string;
  endDate: string;
  totalHoursSaved: number;
  totalCostSaved: number;
  instanceCount: number;
  instances: {
    instanceId: string;
    instanceType: string;
    region: string;
    hoursSaved: number;
    costSaved: number;
  }[];
}

export interface SavingsAccountReport {
  type: "account";
  accountId: string;
  startDate: string;
  endDate: string;
  totalHoursSaved: number;
  totalCostSaved: number;
  totalInstances: number;
  scheduleCount: number;
  schedules: {
    scheduleId: string;
    scheduleName: string;
    hoursSaved: number;
    costSaved: number;
    instanceCount: number;
  }[];
}

export type SavingsReport =
  | SavingsSummaryReport
  | SavingsScheduleReport
  | SavingsAccountReport;

export interface SavingsReportResponse {
  success: true;
  report: SavingsReport;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
