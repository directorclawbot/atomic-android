package com.atomic.app.presentation.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.atomic.app.presentation.theme.AtomicTextStyle
import com.atomic.app.presentation.theme.Spacing

/**
 * Full-screen error state with optional retry action.
 */
@Composable
fun ErrorScreen(
    message: String,
    modifier: Modifier = Modifier,
    details: String? = null,
    onRetry: (() -> Unit)? = null
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            imageVector = Icons.Default.Error,
            contentDescription = null,
            modifier = Modifier.size(56.dp),
            tint = MaterialTheme.colorScheme.error
        )
        Spacer(modifier = Modifier.height(Spacing.sm))
        Text(
            text = "Something went wrong",
            style = AtomicTextStyle.sectionTitle,
            color = MaterialTheme.colorScheme.onSurface
        )
        Spacer(modifier = Modifier.height(Spacing.xxs))
        Text(
            text = message,
            style = AtomicTextStyle.body,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
        if (details != null) {
            Spacer(modifier = Modifier.height(Spacing.xs))
            Text(
                text = details,
                style = AtomicTextStyle.caption,
                color = MaterialTheme.colorScheme.outline,
                textAlign = TextAlign.Center
            )
        }
        if (onRetry != null) {
            Spacer(modifier = Modifier.height(Spacing.lg))
            Button(onClick = onRetry) {
                Text("Retry")
            }
        }
    }
}

/**
 * Compact error message for inline/card contexts.
 */
@Composable
fun ErrorMessage(
    message: String,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null
) {
    Column(
        modifier = modifier.padding(Spacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.Warning,
            contentDescription = null,
            modifier = Modifier.size(IconSize.xxs),
            tint = MaterialTheme.colorScheme.error
        )
        Spacer(modifier = Modifier.height(Spacing.micro))
        Text(
            text = message,
            style = AtomicTextStyle.errorMessage,
            color = MaterialTheme.colorScheme.error,
            textAlign = TextAlign.Center
        )
        if (onRetry != null) {
            Spacer(modifier = Modifier.height(Spacing.xxs))
            Button(onClick = onRetry) {
                Text("Retry", style = AtomicTextStyle.chipLabel)
            }
        }
    }
}

private val IconSize = com.atomic.app.presentation.theme.IconSize