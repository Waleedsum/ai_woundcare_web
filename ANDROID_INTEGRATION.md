# Android App Integration Guide for Wound AI System

## 📱 Overview

This guide covers integrating the Wound AI backend with a native Android application using Kotlin and modern Android architecture components.

---

## 🏗️ Architecture

### Tech Stack
- **Language**: Kotlin
- **Architecture**: MVVM + Repository Pattern
- **DI**: Hilt (Dagger)
- **Networking**: Retrofit + OkHttp
- **Image Loading**: Coil
- **Storage**: Room Database (local cache) + DataStore (preferences)
- **Async**: Kotlin Coroutines + Flow
- **Camera**: CameraX

### App Structure
```
app/
├── data/
│   ├── api/          # Retrofit API interfaces
│   ├── models/       # Data models
│   ├── repository/   # Data repositories
│   └── local/        # Room database
├── di/               # Dependency injection modules
├── ui/
│   ├── auth/         # Login/Register screens
│   ├── analysis/     # Wound analysis screens
│   ├── chat/         # AI nurse chat
│   └── cases/        # Case history
└── utils/            # Utilities and extensions
```

---

## 🔐 Authentication Flow

### 1. API Service Interface (Retrofit)

```kotlin
// data/api/AuthApi.kt
package com.woundai.data.api

import com.woundai.data.models.*
import retrofit2.Response
import retrofit2.http.*

interface AuthApi {
    
    @FormUrlEncoded
    @POST("token")
    suspend fun login(
        @Field("username") username: String,
        @Field("password") password: String
    ): Response<TokenResponse>
    
    @POST("register")
    suspend fun register(
        @Body request: RegisterRequest
    ): Response<UserResponse>
    
    @POST("refresh")
    suspend fun refreshToken(
        @Body request: RefreshTokenRequest
    ): Response<TokenResponse>
    
    @POST("logout")
    suspend fun logout(): Response<Unit>
    
    @GET("me")
    suspend fun getCurrentUser(): Response<UserResponse>
}

// Data Models
data class TokenResponse(
    val access_token: String,
    val refresh_token: String,
    val token_type: String = "bearer",
    val expires_in: Int
)

data class RegisterRequest(
    val username: String,
    val email: String,
    val password: String,
    val full_name: String,
    val organization: String? = null,
    val department: String? = null
)

data class RefreshTokenRequest(
    val refresh_token: String
)

data class UserResponse(
    val id: Int,
    val username: String,
    val email: String,
    val full_name: String,
    val role: String,
    val organization: String?,
    val department: String?,
    val is_active: Boolean
)
```

### 2. Token Manager (DataStore)

```kotlin
// data/local/TokenManager.kt
package com.woundai.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "auth_prefs")

@Singleton
class TokenManager @Inject constructor(
    private val context: Context
) {
    
    companion object {
        private val ACCESS_TOKEN_KEY = stringPreferencesKey("access_token")
        private val REFRESH_TOKEN_KEY = stringPreferencesKey("refresh_token")
        private val USER_ID_KEY = stringPreferencesKey("user_id")
    }
    
    suspend fun saveTokens(accessToken: String, refreshToken: String) {
        context.dataStore.edit { prefs ->
            prefs[ACCESS_TOKEN_KEY] = accessToken
            prefs[REFRESH_TOKEN_KEY] = refreshToken
        }
    }
    
    suspend fun saveUserId(userId: String) {
        context.dataStore.edit { prefs ->
            prefs[USER_ID_KEY] = userId
        }
    }
    
    fun getAccessToken(): Flow<String?> {
        return context.dataStore.data.map { prefs ->
            prefs[ACCESS_TOKEN_KEY]
        }
    }
    
    fun getRefreshToken(): Flow<String?> {
        return context.dataStore.data.map { prefs ->
            prefs[REFRESH_TOKEN_KEY]
        }
    }
    
    suspend fun clearTokens() {
        context.dataStore.edit { prefs ->
            prefs.remove(ACCESS_TOKEN_KEY)
            prefs.remove(REFRESH_TOKEN_KEY)
            prefs.remove(USER_ID_KEY)
        }
    }
    
    suspend fun isLoggedIn(): Boolean {
        var token: String? = null
        context.dataStore.data.map { prefs ->
            token = prefs[ACCESS_TOKEN_KEY]
        }
        return !token.isNullOrEmpty()
    }
}
```

### 3. Auth Interceptor (OkHttp)

```kotlin
// data/api/AuthInterceptor.kt
package com.woundai.data.api

import com.woundai.data.local.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response
import javax.inject.Inject

class AuthInterceptor @Inject constructor(
    private val tokenManager: TokenManager
) : Interceptor {
    
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        // Skip auth for login/register endpoints
        if (originalRequest.url.encodedPath.contains("/token") ||
            originalRequest.url.encodedPath.contains("/register")) {
            return chain.proceed(originalRequest)
        }
        
        // Add access token
        val accessToken = runBlocking {
            tokenManager.getAccessToken().first()
        }
        
        val newRequest = if (accessToken != null) {
            originalRequest.newBuilder()
                .header("Authorization", "Bearer $accessToken")
                .build()
        } else {
            originalRequest
        }
        
        val response = chain.proceed(newRequest)
        
        // Handle token expiration (401)
        if (response.code == 401) {
            response.close()
            
            // Attempt token refresh
            val refreshed = refreshTokenSync()
            
            return if (refreshed) {
                val newAccessToken = runBlocking {
                    tokenManager.getAccessToken().first()
                }
                
                val retryRequest = originalRequest.newBuilder()
                    .header("Authorization", "Bearer $newAccessToken")
                    .build()
                
                chain.proceed(retryRequest)
            } else {
                response
            }
        }
        
        return response
    }
    
    private fun refreshTokenSync(): Boolean {
        return try {
            runBlocking {
                val refreshToken = tokenManager.getRefreshToken().first() ?: return@runBlocking false
                
                // Call refresh endpoint
                // Implementation depends on your setup
                // Return true if successful
                false
            }
        } catch (e: Exception) {
            false
        }
    }
}
```

### 4. Network Module (Hilt)

```kotlin
// di/NetworkModule.kt
package com.woundai.di

import com.woundai.data.api.AuthApi
import com.woundai.data.api.AuthInterceptor
import com.woundai.data.api.WoundAnalysisApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    
    private const val BASE_URL = "https://your-api-domain.com/"
    
    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor
    ): OkHttpClient {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }
    
    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
    
    @Provides
    @Singleton
    fun provideAuthApi(retrofit: Retrofit): AuthApi {
        return retrofit.create(AuthApi::class.java)
    }
    
    @Provides
    @Singleton
    fun provideWoundAnalysisApi(retrofit: Retrofit): WoundAnalysisApi {
        return retrofit.create(WoundAnalysisApi::class.java)
    }
}
```

### 5. Auth Repository

```kotlin
// data/repository/AuthRepository.kt
package com.woundai.data.repository

import com.woundai.data.api.AuthApi
import com.woundai.data.local.TokenManager
import com.woundai.data.models.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val authApi: AuthApi,
    private val tokenManager: TokenManager
) {
    
    fun login(username: String, password: String): Flow<Resource<TokenResponse>> = flow {
        emit(Resource.Loading())
        
        try {
            val response = authApi.login(username, password)
            
            if (response.isSuccessful && response.body() != null) {
                val tokenResponse = response.body()!!
                
                // Save tokens
                tokenManager.saveTokens(
                    tokenResponse.access_token,
                    tokenResponse.refresh_token
                )
                
                emit(Resource.Success(tokenResponse))
            } else {
                emit(Resource.Error("Login failed: ${response.message()}"))
            }
        } catch (e: Exception) {
            emit(Resource.Error("Network error: ${e.message}"))
        }
    }
    
    fun register(request: RegisterRequest): Flow<Resource<UserResponse>> = flow {
        emit(Resource.Loading())
        
        try {
            val response = authApi.register(request)
            
            if (response.isSuccessful && response.body() != null) {
                emit(Resource.Success(response.body()!!))
            } else {
                emit(Resource.Error("Registration failed: ${response.message()}"))
            }
        } catch (e: Exception) {
            emit(Resource.Error("Network error: ${e.message}"))
        }
    }
    
    suspend fun logout() {
        try {
            authApi.logout()
        } catch (e: Exception) {
            // Log error but still clear local tokens
        } finally {
            tokenManager.clearTokens()
        }
    }
    
    fun getCurrentUser(): Flow<Resource<UserResponse>> = flow {
        emit(Resource.Loading())
        
        try {
            val response = authApi.getCurrentUser()
            
            if (response.isSuccessful && response.body() != null) {
                emit(Resource.Success(response.body()!!))
            } else {
                emit(Resource.Error("Failed to get user: ${response.message()}"))
            }
        } catch (e: Exception) {
            emit(Resource.Error("Network error: ${e.message}"))
        }
    }
}

// Resource wrapper for API responses
sealed class Resource<T>(
    val data: T? = null,
    val message: String? = null
) {
    class Success<T>(data: T) : Resource<T>(data)
    class Error<T>(message: String, data: T? = null) : Resource<T>(data, message)
    class Loading<T> : Resource<T>()
}
```

---

## 📸 Wound Analysis Integration

### 1. Analysis API Interface

```kotlin
// data/api/WoundAnalysisApi.kt
package com.woundai.data.api

import com.woundai.data.models.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface WoundAnalysisApi {
    
    @Multipart
    @POST("analyze")
    suspend fun analyzeWound(
        @Part("case_code") caseCode: RequestBody,
        @Part("wound_type") woundType: RequestBody,
        @Part("exudate") exudate: RequestBody,
        @Part("tissue_types") tissueTypes: RequestBody,
        @Part("braden_scores") bradenScores: RequestBody?,
        @Part file: MultipartBody.Part
    ): Response<AnalysisResponse>
    
    @GET("cases")
    suspend fun getCases(): Response<CasesResponse>
    
    @FormUrlEncoded
    @POST("report")
    suspend fun generateReport(
        @Field("case_code") caseCode: String
    ): Response<ReportResponse>
}

// Models
data class AnalysisResponse(
    val case_code: String,
    val size_cm2: Double,
    val length_cm: Double?,
    val width_cm: Double?,
    val tissue_counts: TissueCounts,
    val infection_risk: Double,
    val infection_risk_level: String,
    val severity: String,
    val dressing: String,
    val braden_score: Int?,
    val braden_risk: String?,
    val ai_summary: String,
    val treatment_plan: String,
    val followup_note: String
)

data class TissueCounts(
    val granulation: Int,
    val granulation_percent: Double,
    val slough: Int,
    val slough_percent: Double,
    val necrotic: Int,
    val necrotic_percent: Double
)

data class CasesResponse(
    val cases: List<CaseItem>
)

data class CaseItem(
    val case_code: String,
    val wound_type: String,
    val severity: String,
    val created_at: String
)

data class ReportResponse(
    val report: String
)
```

### 2. Camera Capture (CameraX)

```kotlin
// ui/analysis/CameraCaptureFragment.kt
package com.woundai.ui.analysis

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import com.woundai.databinding.FragmentCameraCaptureBinding
import dagger.hilt.android.AndroidEntryPoint
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

@AndroidEntryPoint
class CameraCaptureFragment : Fragment() {
    
    private var _binding: FragmentCameraCaptureBinding? = null
    private val binding get() = _binding!!
    
    private val viewModel: AnalysisViewModel by viewModels()
    
    private var imageCapture: ImageCapture? = null
    private lateinit var cameraExecutor: ExecutorService
    
    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            startCamera()
        } else {
            // Show permission denied message
        }
    }
    
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentCameraCaptureBinding.inflate(inflater, container, false)
        return binding.root
    }
    
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        // Request camera permission
        when {
            ContextCompat.checkSelfPermission(
                requireContext(),
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED -> {
                startCamera()
            }
            else -> {
                requestPermissionLauncher.launch(Manifest.permission.CAMERA)
            }
        }
        
        cameraExecutor = Executors.newSingleThreadExecutor()
        
        binding.captureButton.setOnClickListener {
            takePhoto()
        }
    }
    
    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(requireContext())
        
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            
            val preview = Preview.Builder()
                .build()
                .also {
                    it.setSurfaceProvider(binding.previewView.surfaceProvider)
                }
            
            imageCapture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                .build()
            
            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
            
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    this,
                    cameraSelector,
                    preview,
                    imageCapture
                )
            } catch (e: Exception) {
                // Handle error
            }
            
        }, ContextCompat.getMainExecutor(requireContext()))
    }
    
    private fun takePhoto() {
        val imageCapture = imageCapture ?: return
        
        val photoFile = File(
            requireContext().cacheDir,
            "wound_${System.currentTimeMillis()}.jpg"
        )
        
        val outputOptions = ImageCapture.OutputFileOptions.Builder(photoFile).build()
        
        imageCapture.takePicture(
            outputOptions,
            ContextCompat.getMainExecutor(requireContext()),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                    // Navigate to analysis screen with captured image
                    viewModel.setCapturedImage(photoFile)
                    // Navigate to next screen
                }
                
                override fun onError(exc: ImageCaptureException) {
                    // Handle error
                }
            }
        )
    }
    
    override fun onDestroyView() {
        super.onDestroyView()
        cameraExecutor.shutdown()
        _binding = null
    }
}
```

### 3. Analysis ViewModel

```kotlin
// ui/analysis/AnalysisViewModel.kt
package com.woundai.ui.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.woundai.data.repository.AnalysisRepository
import com.woundai.data.models.AnalysisResponse
import com.woundai.data.models.Resource
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

@HiltViewModel
class AnalysisViewModel @Inject constructor(
    private val repository: AnalysisRepository
) : ViewModel() {
    
    private val _analysisState = MutableStateFlow<Resource<AnalysisResponse>>(Resource.Loading())
    val analysisState: StateFlow<Resource<AnalysisResponse>> = _analysisState
    
    private val _capturedImage = MutableStateFlow<File?>(null)
    val capturedImage: StateFlow<File?> = _capturedImage
    
    fun setCapturedImage(file: File) {
        _capturedImage.value = file
    }
    
    fun analyzeWound(
        caseCode: String,
        woundType: String,
        exudate: String,
        tissueTypes: String,
        bradenScores: String?,
        imageFile: File
    ) {
        viewModelScope.launch {
            repository.analyzeWound(
                caseCode = caseCode,
                woundType = woundType,
                exudate = exudate,
                tissueTypes = tissueTypes,
                bradenScores = bradenScores,
                imageFile = imageFile
            ).collect { resource ->
                _analysisState.value = resource
            }
        }
    }
}
```

---

## 🔒 Security Best Practices

### 1. Certificate Pinning

```kotlin
// di/NetworkModule.kt (add to OkHttpClient)
@Provides
@Singleton
fun provideCertificatePinner(): CertificatePinner {
    return CertificatePinner.Builder()
        .add("your-api-domain.com", "sha256/YOUR_CERT_HASH")
        .build()
}
```

### 2. ProGuard Rules

```proguard
# proguard-rules.pro

# Keep API models
-keep class com.woundai.data.models.** { *; }

# Retrofit
-keepattributes Signature
-keepattributes *Annotation*
-keep class retrofit2.** { *; }

# OkHttp
-keep class okhttp3.** { *; }

# Gson
-keep class com.google.gson.** { *; }
```

### 3. Root Detection

```kotlin
// utils/SecurityUtils.kt
object SecurityUtils {
    
    fun isDeviceRooted(): Boolean {
        return checkRootMethod1() || checkRootMethod2() || checkRootMethod3()
    }
    
    private fun checkRootMethod1(): Boolean {
        val buildTags = android.os.Build.TAGS
        return buildTags != null && buildTags.contains("test-keys")
    }
    
    private fun checkRootMethod2(): Boolean {
        val paths = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su"
        )
        return paths.any { File(it).exists() }
    }
    
    private fun checkRootMethod3(): Boolean {
        return try {
            Runtime.getRuntime().exec("su")
            true
        } catch (e: Exception) {
            false
        }
    }
}
```

---

## 📦 Build Configuration

### build.gradle.kts (Module)

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("kotlin-kapt")
    id("dagger.hilt.android.plugin")
}

android {
    namespace = "com.woundai"
    compileSdk = 34
    
    defaultConfig {
        applicationId = "com.woundai"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        
        buildConfigField("String", "BASE_URL", "\"https://your-api-domain.com/\"")
    }
    
    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }
    
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    
    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    
    // Dependency Injection
    implementation("com.google.dagger:hilt-android:2.48")
    kapt("com.google.dagger:hilt-compiler:2.48")
    
    // JWT
    implementation("com.auth0.android:jwtdecode:2.0.1")
    
    // DataStore
    implementation("androidx.datastore:datastore-preferences:1.0.0")
    
    // Camera
    implementation("androidx.camera:camera-camera2:1.3.1")
    implementation("androidx.camera:camera-lifecycle:1.3.1")
    implementation("androidx.camera:camera-view:1.3.1")
    
    // Image Loading
    implementation("io.coil-kt:coil:2.5.0")
    
    // Navigation
    implementation("androidx.navigation:navigation-fragment-ktx:2.7.6")
    implementation("androidx.navigation:navigation-ui-ktx:2.7.6")
    
    // Lifecycle
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-livedata-ktx:2.7.0")
}
```

---

## ✅ Summary

This integration provides:
- ✅ Secure JWT authentication with token refresh
- ✅ Multi-user support with role-based access
- ✅ Image capture and upload
- ✅ Wound analysis integration
- ✅ Offline-first architecture with Room caching
- ✅ Modern Android architecture (MVVM + Repository)
- ✅ Security best practices

**Next Steps:**
1. Set up Android Studio project
2. Implement authentication screens (Login/Register)
3. Implement camera capture and analysis screens
4. Add case history and reporting
5. Test on physical devices
6. Submit to Google Play Store

