# EcoScheduler - AWS EC2 Cost Optimization Tool

EcoScheduler is a serverless application that helps optimize AWS EC2 costs by automating instance scheduling. This tool enables you to automatically start and stop EC2 instances based on predefined schedules, saving money on instances that don't need to run 24/7.

## Features

- **Automated EC2 Scheduling**: Define cron-based schedules for starting and stopping EC2 instances
- **Cross-Account Management**: Manage EC2 instances across multiple AWS accounts
- **Exception Handling**: Define exception dates (holidays, maintenance periods) when the normal schedule shouldn't apply
- **Cost Savings Reporting**: Track and report on cost savings achieved through instance scheduling
- **Role-Based Access Control**: Different permission levels for administrators, developers, and finance users
- **Serverless Architecture**: Built entirely on AWS serverless services for minimal operational overhead

## Architecture

EcoScheduler is built using AWS serverless technologies:

- **AWS Lambda**: For all backend functionality
- **Amazon API Gateway**: For API endpoints
- **Amazon DynamoDB**: For data storage
- **Amazon EventBridge**: For scheduling EC2 instance operations
- **AWS IAM**: For cross-account access control

## Getting Started

### Prerequisites

- Node.js 14+ and npm
- Python 3.10+
- AWS CLI configured with appropriate permissions
- Serverless Framework CLI (`npm install -g serverless`)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/eco-scheduler.git
   cd eco-scheduler
   ```

2. Install backend dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   npm install
   ```

3. Deploy the backend:
   ```
   cd backend
   serverless deploy --stage dev
   ```

4. Set up customer account role (to be run in each AWS account you want to manage):
   ```
   aws cloudformation create-stack --stack-name EcoScheduler-CrossAccount-Role --template-body file://backend/infra/customer-account-role.yml --capabilities CAPABILITY_NAMED_IAM --parameters ParameterKey=MasterAccountId,ParameterValue=<your-master-account-id>
   ```

### Usage

After deployment, you can:

1. Create user accounts for your team with appropriate roles
2. Connect AWS accounts you want to manage
3. Create schedules for EC2 instances
4. Monitor cost savings through the integrated reporting

## Project Structure

```
EcoScheduler/
├── backend/
│   ├── src/
│   │   ├── common/                # Shared code and utilities
│   │   ├── functions/             # Lambda function handlers
│   │   └── models/                # Business logic and data models
│   ├── tests/                     # Unit and integration tests
│   └── infra/                     # Infrastructure as Code
└── frontend/                      # Frontend code (to be implemented)
```

## Role-Based Access

EcoScheduler supports three user roles:

- **Admin**: Full access to manage schedules, users, and view reports
- **Developer**: View assigned instances, create schedules, request overrides
- **Finance**: View savings reports and export data

## Security Considerations

EcoScheduler is designed with security in mind:

- Uses JWT authentication for API calls
- Implements cross-account IAM roles with least privilege
- Stores no AWS credentials in the application
- All data stored in DynamoDB is encrypted at rest

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details.