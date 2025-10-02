@description('The name of the resource group')
param resourceGroupName string = 'rg-rfpo-${uniqueString(subscription().subscriptionId)}'

@description('The location for all resources')
param location string = resourceGroup().location

@description('The name of the container apps environment')
param environmentName string = 'rfpo-env-${uniqueString(resourceGroup().id)}'

@description('The name of the container registry')
param acrName string = 'acrrfpo${uniqueString(resourceGroup().id)}'

@description('The name of the storage account')
param storageAccountName string = 'strfpo${uniqueString(resourceGroup().id)}'

@description('The name of the file share for database storage')
param fileShareName string = 'rfpo-data'

@description('Environment type (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environmentType string = 'dev'

// Variables
var tags = {
  project: 'rfpo-application'
  environment: environmentType
  owner: 'rfpo-team'
}

var containerAppNames = {
  api: 'rfpo-api'
  admin: 'rfpo-admin'
  user: 'rfpo-user'
}

// Azure Container Registry
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Storage Account for persistent data
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// File Service
resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

// File Share for database and uploads
resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileService
  name: fileShareName
  properties: {
    shareQuota: 5120 // 5GB
    enabledProtocols: 'SMB'
  }
}

// PostgreSQL Flexible Server
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: 'rfpo-db-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: 'rfpoadmin'
    administratorLoginPassword: 'RfpoSecure123!'
    version: '14'
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    maintenanceWindow: {
      customWindow: 'Disabled'
    }
  }
}

// PostgreSQL Database
resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgresServer
  name: 'rfpodb'
  properties: {
    charset: 'utf8'
    collation: 'en_US.utf8'
  }
}

// PostgreSQL Firewall Rules to allow Azure services
resource postgresFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Container Apps Environment

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-rfpo-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Apps Environment
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

// Storage configuration for Container Apps
resource storageConfig 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: containerAppsEnvironment
  name: 'rfpo-storage'
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: fileShare.name
      accessMode: 'ReadWrite'
    }
  }
}

// RFPO API Container App
resource apiContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppNames.api
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 5002
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'jwt-secret'
          value: 'jwt-secret-key-${uniqueString(resourceGroup().id)}-production'
        }
        {
          name: 'api-secret'
          value: 'api-secret-key-${uniqueString(resourceGroup().id)}-production'
        }
        {
          name: 'database-url'
          value: 'postgresql://rfpoadmin:RfpoSecure123!@${postgresServer.properties.fullyQualifiedDomainName}:5432/rfpodb?sslmode=require'
        }
      ]
    }
    template: {
      containers: [
        {
          image: '${acr.properties.loginServer}/rfpo-api:latest'
          name: 'rfpo-api'
          env: [
            {
              name: 'JWT_SECRET_KEY'
              secretRef: 'jwt-secret'
            }
            {
              name: 'API_SECRET_KEY'
              secretRef: 'api-secret'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'FLASK_ENV'
              value: environmentType == 'prod' ? 'production' : 'development'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'data-volume'
              mountPath: '/app/data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
      volumes: [
        {
          name: 'data-volume'
          storageType: 'AzureFile'
          storageName: storageConfig.name
        }
      ]
    }
  }
}

// RFPO Admin Container App
resource adminContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppNames.admin
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 5111
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'admin-secret'
          value: 'admin-secret-key-${uniqueString(resourceGroup().id)}-production'
        }
        {
          name: 'database-url'
          value: 'postgresql://rfpoadmin:RfpoSecure123!@${postgresServer.properties.fullyQualifiedDomainName}:5432/rfpodb?sslmode=require'
        }
      ]
    }
    template: {
      containers: [
        {
          image: '${acr.properties.loginServer}/rfpo-admin:latest'
          name: 'rfpo-admin'
          env: [
            {
              name: 'ADMIN_SECRET_KEY'
              secretRef: 'admin-secret'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'FLASK_ENV'
              value: environmentType == 'prod' ? 'production' : 'development'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          volumeMounts: [
            {
              volumeName: 'data-volume'
              mountPath: '/app/data'
            }
            {
              volumeName: 'uploads-volume'
              mountPath: '/app/uploads'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
      volumes: [
        {
          name: 'data-volume'
          storageType: 'AzureFile'
          storageName: storageConfig.name
        }
        {
          name: 'uploads-volume'
          storageType: 'AzureFile'
          storageName: storageConfig.name
        }
      ]
    }
  }
}

// RFPO User App Container App
resource userContainerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppNames.user
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 5000
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'user-app-secret'
          value: 'user-app-secret-${uniqueString(resourceGroup().id)}-production'
        }
        {
          name: 'database-url'
          value: 'postgresql://rfpoadmin:RfpoSecure123!@${postgresServer.properties.fullyQualifiedDomainName}:5432/rfpodb?sslmode=require'
        }
      ]
    }
    template: {
      containers: [
        {
          image: '${acr.properties.loginServer}/rfpo-user:latest'
          name: 'rfpo-user'
          env: [
            {
              name: 'USER_APP_SECRET_KEY'
              secretRef: 'user-app-secret'
            }
            {
              name: 'API_BASE_URL'
              value: 'https://${apiContainerApp.properties.configuration.ingress.fqdn}/api'
            }
            {
              name: 'FLASK_ENV'
              value: environmentType == 'prod' ? 'production' : 'development'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

// Outputs
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output storageAccountName string = storageAccount.name
output fileShareName string = fileShare.name
output containerAppsEnvironmentName string = containerAppsEnvironment.name
output apiUrl string = 'https://${apiContainerApp.properties.configuration.ingress.fqdn}'
output adminUrl string = 'https://${adminContainerApp.properties.configuration.ingress.fqdn}'
output userUrl string = 'https://${userContainerApp.properties.configuration.ingress.fqdn}'
output resourceGroupName string = resourceGroup().name
