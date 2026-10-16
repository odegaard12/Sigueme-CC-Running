plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "cc.sigueme.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "cc.sigueme.app"
        minSdk = 26
        targetSdk = 34
        versionCode = (System.getenv("VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("VERSION_NAME") ?: "dev"
    }
    // firma fija (secreto del repo en GitHub Actions): así una versión nueva se
    // instala encima de la vieja sin desinstalar
    signingConfigs {
        create("fija") {
            val ks = System.getenv("FIRMA_FICHERO")
            if (ks != null) {
                storeFile = file(ks)
                storePassword = System.getenv("FIRMA_CLAVE")
                keyAlias = "sigueme"
                keyPassword = System.getenv("FIRMA_CLAVE")
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (System.getenv("FIRMA_FICHERO") != null) signingConfigs.getByName("fija")
                            else signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    lint { abortOnError = false }
}

dependencies {
    // org.json va dentro de Android, pero en las pruebas de la JVM no: la real
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20240303")
}
