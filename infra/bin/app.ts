#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { StorageStack } from "../lib/storage-stack";
import { AuthStack } from "../lib/auth-stack";

const app = new cdk.App();

// Stacks will be added here as they are implemented:
// - ApiStack (API Gateway + Lambdas)
// - EventsStack (EventBridge)
// - AmplifyStack (Amplify Hosting)

new StorageStack(app, "TravelBuddyStorage", {
  description: "Travel Buddy — S3 and DynamoDB storage resources",
});

new AuthStack(app, "TravelBuddyAuth", {
  description: "Travel Buddy — Cognito authentication resources",
});

app.synth();
