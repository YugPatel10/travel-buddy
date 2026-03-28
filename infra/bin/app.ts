#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";

const app = new cdk.App();

// Stacks will be added here as they are implemented:
// - StorageStack (S3 + DynamoDB)
// - AuthStack (Cognito)
// - ApiStack (API Gateway + Lambdas)
// - EventsStack (EventBridge)
// - AmplifyStack (Amplify Hosting)

app.synth();
