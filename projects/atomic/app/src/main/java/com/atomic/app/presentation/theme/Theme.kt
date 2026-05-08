package com.atomic.app.presentation.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

// ─── Dark Color Scheme ───────────────────────────────────────────────────────
private val DarkColorScheme = darkColorScheme(
    primary = AtomicBlue,
    onPrimary = Color.White,
    primaryContainer = AtomicBlueDark,
    onPrimaryContainer = Color.White,
    secondary = AtomicOrange,
    onSecondary = Color.Black,
    secondaryContainer = AtomicOrangeDark,
    onSecondaryContainer = Color.White,
    tertiary = AtomicTeal,
    onTertiary = Color.White,
    tertiaryContainer = AtomicTeal.copy(alpha = 0.3f),
    onTertiaryContainer = AtomicTealLight,
    background = DarkBackground,
    onBackground = OnDarkSurface,
    surface = DarkSurface,
    onSurface = OnDarkSurface,
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = OnDarkSurfaceVariant,
    surfaceTint = AtomicBlue,
    outline = DarkOutline,
    outlineVariant = DarkOutlineVariant,
    error = ErrorRed,
    onError = Color.White,
    errorContainer = ErrorRedContainer,
    onErrorContainer = Color.White,
    // Additional surface roles
    inverseSurface = LightSurface,
    inverseOnSurface = OnLightSurface,
    inversePrimary = AtomicBlueDark,
    scrim = DarkScrim
)

// ─── Light Color Scheme ──────────────────────────────────────────────────────
private val LightColorScheme = lightColorScheme(
    primary = AtomicBlue,
    onPrimary = Color.White,
    primaryContainer = AtomicBlueLight,
    onPrimaryContainer = Color.Black,
    secondary = AtomicOrange,
    onSecondary = Color.White,
    secondaryContainer = AtomicOrangeLight,
    onSecondaryContainer = Color.Black,
    tertiary = AtomicTeal,
    onTertiary = Color.White,
    tertiaryContainer = AtomicTealLight.copy(alpha = 0.3f),
    onTertiaryContainer = Color.Black,
    background = LightBackground,
    onBackground = OnLightSurface,
    surface = LightSurface,
    onSurface = OnLightSurface,
    surfaceVariant = LightSurfaceVariant,
    onSurfaceVariant = OnLightSurfaceVariant,
    surfaceTint = AtomicBlue,
    outline = LightOutline,
    outlineVariant = LightOutlineVariant,
    error = ErrorRed,
    onError = Color.White,
    errorContainer = ErrorRedContainer,
    onErrorContainer = Color.White,
    // Additional surface roles
    inverseSurface = DarkSurface,
    inverseOnSurface = OnDarkSurface,
    inversePrimary = AtomicBlueLight,
    scrim = LightScrim
)

// ─── Theme ───────────────────────────────────────────────────────────────────
/**
 * Atomic theme supporting light, dark, and system-follow modes,
 * plus dynamic color on Android 12+ (API 31+).
 */
@Composable
fun AtomicTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            // Status bar
            window.statusBarColor = colorScheme.surface.toArgb()
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !darkTheme
                isAppearanceLightNavigationBars = !darkTheme
            }
            // Navigation bar
            window.navigationBarColor = colorScheme.surface.toArgb()
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}

// ─── Status Color Helpers ─────────────────────────────────────────────────────
object AtomicStatusColors {
    @Composable
    fun success() = SuccessGreen

    @Composable
    fun successContainer() = SuccessGreenContainer

    @Composable
    fun warning() = WarningYellow

    @Composable
    fun warningContainer() = WarningYellowContainer

    @Composable
    fun error() = ErrorRed

    @Composable
    fun errorContainer() = ErrorRedContainer

    @Composable
    fun info() = InfoBlue

    @Composable
    fun infoContainer() = InfoBlueContainer
}