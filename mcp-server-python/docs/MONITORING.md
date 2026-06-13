# Monitoring Guide for Vertex AI Memory Bank MCP Server

This guide covers monitoring and alerting configuration for the Cloud Run deployment.

## Cloud Run Logging

### View Logs

View logs using gcloud CLI:

```bash
gcloud run services logs read openreflect-mcp \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --limit 50
```

### Stream Logs

Stream logs in real-time:

```bash
gcloud run services logs tail openreflect-mcp \
  --region us-central1 \
  --project YOUR_PROJECT_ID
```

### Filter Logs

Filter logs by severity:

```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=openreflect-mcp AND \
  severity>=ERROR" \
  --limit 50 \
  --project YOUR_PROJECT_ID
```

## Cloud Monitoring Metrics

### Key Metrics

The following metrics are automatically collected:

1. **Request Count** (`run.googleapis.com/request_count`)
   - Total number of requests
   - Filtered by response code class (2xx, 4xx, 5xx)

2. **Request Latency** (`run.googleapis.com/request_latencies`)
   - P50, P95, P99 latencies
   - Critical for performance monitoring

3. **Container Instance Count** (`run.googleapis.com/container/instance_count`)
   - Number of active container instances
   - Useful for scaling analysis

4. **Container Health Check Status** (`run.googleapis.com/container/health_check_status`)
   - Health check pass/fail status
   - Critical for availability monitoring

5. **Memory Utilization** (`run.googleapis.com/container/memory/utilizations`)
   - Memory usage percentage
   - Important for resource planning

6. **CPU Utilization** (`run.googleapis.com/container/cpu/utilizations`)
   - CPU usage percentage
   - Important for performance tuning

### Custom Metrics

You can create custom metrics for MCP-specific operations:

```bash
# Example: Track memory operations
gcloud logging write openreflect-mcp-metrics \
  '{"operation":"generate_memories","duration_ms":1500,"success":true}' \
  --project YOUR_PROJECT_ID
```

## Alert Policies

### Setup Alerts

Use the `monitoring.yaml` file to create alert policies:

```bash
gcloud alpha monitoring policies create --policy-from-file=monitoring.yaml \
  --project YOUR_PROJECT_ID
```

### Manual Alert Creation

Create alerts via Cloud Console:

1. Go to **Cloud Console > Monitoring > Alerting**
2. Click **Create Policy**
3. Configure conditions:
   - **High Error Rate**: Error rate > 5% for 5 minutes
   - **High Latency**: P95 latency > 5 seconds for 5 minutes
   - **Service Unavailable**: Health check failing for 1 minute

### Notification Channels

Set up notification channels:

```bash
# Email channel
gcloud alpha monitoring channels create \
  --display-name="Memory Bank MCP Alerts" \
  --type=email \
  --channel-labels=email_address=your-email@example.com \
  --project YOUR_PROJECT_ID

# Slack channel (requires webhook URL)
gcloud alpha monitoring channels create \
  --display-name="Memory Bank MCP Slack" \
  --type=slack \
  --channel-labels=url=https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  --project YOUR_PROJECT_ID
```

## Dashboards

### Create Dashboard

1. Go to **Cloud Console > Monitoring > Dashboards**
2. Click **Create Dashboard**
3. Add widgets for:
   - Request rate (line chart)
   - Request latency P95 (line chart)
   - Error rate (line chart)
   - Container instances (line chart)
   - Memory utilization (line chart)
   - CPU utilization (line chart)

### Dashboard Queries

Example MQL queries for dashboard widgets:

**Request Rate:**
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name == 'openreflect-mcp'
| group_by 1m, [value_request_count_sum: sum(value.request_count)]
| every 1m
```

**P95 Latency:**
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_latencies'
| filter resource.service_name == 'openreflect-mcp'
| group_by 1m, [value_latency_p95: percentile(value.latency, 95)]
| every 1m
```

**Error Rate:**
```
fetch cloud_run_revision
| metric 'run.googleapis.com/request_count'
| filter resource.service_name == 'openreflect-mcp'
| filter metric.response_code_class == '5xx'
| group_by 1m, [value_error_count_sum: sum(value.request_count)]
| every 1m
```

## Log-Based Metrics

Create log-based metrics for MCP operations:

```bash
# Memory generation operations
gcloud logging metrics create mcp_generate_memories \
  --description="Count of memory generation operations" \
  --log-filter='resource.type="cloud_run_revision" AND
    resource.labels.service_name="openreflect-mcp" AND
    jsonPayload.operation="generate_memories"' \
  --project YOUR_PROJECT_ID

# Memory retrieval operations
gcloud logging metrics create mcp_retrieve_memories \
  --description="Count of memory retrieval operations" \
  --log-filter='resource.type="cloud_run_revision" AND
    resource.labels.service_name="openreflect-mcp" AND
    jsonPayload.operation="retrieve_memories"' \
  --project YOUR_PROJECT_ID
```

## SLO Configuration

### Availability SLO

Target: 99.9% availability (less than 43 minutes downtime per month)

```bash
gcloud alpha monitoring slo create \
  --service=openreflect-mcp \
  --slo-id=availability-slo \
  --display-name="Availability SLO" \
  --goal=0.999 \
  --rolling-period=30d \
  --project YOUR_PROJECT_ID
```

### Latency SLO

Target: 95% of requests complete in under 2 seconds

```bash
gcloud alpha monitoring slo create \
  --service=openreflect-mcp \
  --slo-id=latency-slo \
  --display-name="Latency SLO" \
  --goal=0.95 \
  --rolling-period=30d \
  --project YOUR_PROJECT_ID
```

## Troubleshooting

### High Error Rate

1. Check logs for error patterns:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND \
     resource.labels.service_name=openreflect-mcp AND \
     severity>=ERROR" \
     --limit 100 \
     --format json \
     --project YOUR_PROJECT_ID
   ```

2. Check Vertex AI API status
3. Verify service account permissions
4. Review memory limits and resource allocation

### High Latency

1. Check P95/P99 latency metrics
2. Review container instance count (may need more instances)
3. Check Vertex AI API response times
4. Review memory operations (may be memory-intensive)

### Service Unavailable

1. Check health endpoint: `curl https://SERVICE_URL/health`
2. Review startup logs for initialization errors
3. Verify environment variables are set correctly
4. Check service account has correct permissions

## Best Practices

1. **Set up alerts early**: Configure alerts before production deployment
2. **Monitor key metrics**: Focus on error rate, latency, and availability
3. **Review logs regularly**: Check logs weekly for patterns
4. **Set up dashboards**: Create dashboards for quick visibility
5. **Test alerts**: Verify alert notifications work correctly
6. **Document incidents**: Keep track of incidents and resolutions

## Cost Optimization

- Use log sampling for high-volume logs
- Set appropriate retention periods
- Use metric filters to reduce data collection
- Review and optimize alert frequency
