# 🔧 Render Persistent Disk Debug Guide

## 📋 Current Status
✅ **Changes Deployed**: Commit `da53ec7` with comprehensive debug information
✅ **Debug Functions Added**: Enhanced database path logic and troubleshooting tools
✅ **Auto-Deployment**: Render should be rebuilding your application now

## 🔍 Step-by-Step Debug Process

### 1. Check Render Deployment Status
1. Go to your Render dashboard
2. Navigate to your web service
3. Check the "Events" tab for the latest deployment
4. Wait for deployment to complete (should show "Live" status)

### 2. Examine Debug Output in Render Logs
1. In your Render service dashboard, click on "Logs"
2. Look for the debug output that starts with:
   ```
   🔍 DEBUG: INFORMACIÓN DE BASE DE DATOS
   ```
3. This will show you:
   - RENDER environment variable status
   - DATABASE_PATH configuration
   - Actual database file path being used
   - Directory structure and file existence
   - Table counts and connection status

### 3. Verify Environment Variables
**Critical Check**: Ensure these environment variables are set in Render:

#### Required Environment Variables:
```bash
DATABASE_PATH=/opt/render/project/src/data/usuarios.db
SECRET_KEY=your-secret-key-here
```

#### How to Set Environment Variables in Render:
1. Go to your web service in Render dashboard
2. Click on "Environment" tab
3. Add/verify these variables:
   - **Key**: `DATABASE_PATH`
   - **Value**: `/opt/render/project/src/data/usuarios.db`

### 4. Verify Persistent Disk Configuration
**Check your Render disk settings:**

1. In Render dashboard, go to "Disks" section
2. Verify your persistent disk is:
   - **Name**: `data-disk` (or your chosen name)
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: At least 1GB
   - **Status**: Active

### 5. Test Database Access
Once deployed, visit your application and:
1. Go to admin panel
2. Try to access profitability section
3. Check if data persists after making changes

## 🚨 Common Issues and Solutions

### Issue 1: DATABASE_PATH Not Set
**Symptoms**: Debug shows "DATABASE_PATH: No configurado"
**Solution**: Add DATABASE_PATH environment variable in Render

### Issue 2: Directory Creation Fails
**Symptoms**: Debug shows directory creation errors
**Solution**: Verify disk mount path matches DATABASE_PATH directory

### Issue 3: Database File Not Found
**Symptoms**: Debug shows database file doesn't exist
**Solution**: Check if persistent disk is properly mounted

### Issue 4: Permission Issues
**Symptoms**: Cannot write to database file
**Solution**: Verify Render has write permissions to mounted disk

## 📊 Expected Debug Output (Success)
```
🔍 DEBUG: INFORMACIÓN DE BASE DE DATOS
RENDER: 1
DATABASE_PATH: /opt/render/project/src/data/usuarios.db
Ruta de BD configurada: /opt/render/project/src/data/usuarios.db
Directorio de BD: /opt/render/project/src/data
¿Directorio existe?: True
¿Archivo BD existe?: True
Tablas encontradas: 15
Conexión exitosa: True
```

## 📊 Problematic Debug Output (Needs Fix)
```
🔍 DEBUG: INFORMACIÓN DE BASE DE DATOS
RENDER: 1
DATABASE_PATH: No configurado
Ruta de BD configurada: usuarios.db
¿Archivo BD existe?: False
Error de conexión: [error details]
```

## 🔄 Next Steps After Checking Debug Output

### If DATABASE_PATH is Missing:
1. Add the environment variable in Render
2. Redeploy the service
3. Check logs again

### If Directory/File Issues:
1. Verify persistent disk mount path
2. Check disk is active and properly sized
3. Restart the service if needed

### If Everything Looks Correct But Still Not Working:
1. Try accessing the application
2. Create some test data
3. Restart the service and check if data persists
4. Review Render disk documentation for any recent changes

## 📞 What to Report Back
Please share:
1. **Deployment Status**: Is the new version deployed and live?
2. **Debug Output**: Copy the complete debug information from Render logs
3. **Environment Variables**: Confirm DATABASE_PATH is set correctly
4. **Disk Status**: Verify persistent disk is active and mounted
5. **Application Behavior**: Does data persist after service restarts?

## 🎯 Expected Resolution
With the enhanced debug information, we should be able to:
1. Identify exactly where the persistent disk configuration is failing
2. See if the DATABASE_PATH is being used correctly
3. Verify if the database file is being created in the right location
4. Confirm data persistence between deployments

The debug output will give us the exact information needed to resolve the "los datos persistentes del disk no se pueden ver en la web" issue.
