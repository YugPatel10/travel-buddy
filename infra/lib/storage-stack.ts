import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import { Construct } from "constructs";

export class StorageStack extends cdk.Stack {
  public readonly documentsBucket: s3.Bucket;
  public readonly tripsTable: dynamodb.Table;
  public readonly scoutResultsTable: dynamodb.Table;
  public readonly documentsTable: dynamodb.Table;
  public readonly agentRunsTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.documentsBucket = new s3.Bucket(this, "DocumentsBucket", {
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      enforceSSL: true,

      cors: [
        {
          allowedOrigins: ["*"],
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.PUT,
            s3.HttpMethods.POST,
          ],
          allowedHeaders: ["*"],
          exposedHeaders: ["ETag"],
          maxAge: 3600,
        },
      ],

      lifecycleRules: [
        {
          id: "AbortIncompleteMultipartUploads",
          abortIncompleteMultipartUploadAfter: cdk.Duration.days(7),
        },
        {
          id: "TransitionToIA",
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
        {
          id: "ExpireOldVersions",
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
    });

    new cdk.CfnOutput(this, "DocumentsBucketName", {
      value: this.documentsBucket.bucketName,
      description: "S3 bucket for travel document uploads",
    });

    // Trips table: PK = USER#<userId>, SK = TRIP#<tripId>
    this.tripsTable = new dynamodb.Table(this, "TripsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // ScoutResults table: PK = TRIP#<tripId>, SK = SCOUT#<timestamp>#<type>
    // TTL on old results (30 days)
    this.scoutResultsTable = new dynamodb.Table(this, "ScoutResultsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      timeToLiveAttribute: "TTL",
    });

    // Documents table: PK = USER#<userId>, SK = DOC#<docId>
    this.documentsTable = new dynamodb.Table(this, "DocumentsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // AgentRuns table: PK = TRIP#<tripId>, SK = RUN#<runId>
    this.agentRunsTable = new dynamodb.Table(this, "AgentRunsTable", {
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      timeToLiveAttribute: "TTL",
    });

    new cdk.CfnOutput(this, "TripsTableName", {
      value: this.tripsTable.tableName,
    });
    new cdk.CfnOutput(this, "ScoutResultsTableName", {
      value: this.scoutResultsTable.tableName,
    });
    new cdk.CfnOutput(this, "DocumentsTableName", {
      value: this.documentsTable.tableName,
    });
    new cdk.CfnOutput(this, "AgentRunsTableName", {
      value: this.agentRunsTable.tableName,
    });
  }
}
