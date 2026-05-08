package com.atomic.app.presentation.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.atomic.app.presentation.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onNavigateBack: () -> Unit,
    serverUrl: String = "",
    onServerUrlChange: (String) -> Unit = {},
    onSaveServer: () -> Unit = {},
    isConnected: Boolean = false
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings", style = AtomicTextStyle.screenTitle) },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(Spacing.screen),
            verticalArrangement = Arrangement.spacedBy(Spacing.lg)
        ) {
            // ── Server Connection Section ────────────────────────────────────
            SettingsSection(title = "Server Connection") {
                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = onServerUrlChange,
                    label = { Text("Komga Server URL") },
                    placeholder = { Text("https://komga.example.com") },
                    leadingIcon = { Icon(Icons.Default.Cloud, contentDescription = null) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    isError = serverUrl.isNotEmpty() && !serverUrl.startsWith("http")
                )
                Spacer(modifier = Modifier.height(Spacing.sm))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (isConnected) {
                        Icon(
                            Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = SuccessGreen,
                            modifier = Modifier.size(IconSize.xxs)
                        )
                        Text(
                            "Connected",
                            style = AtomicTextStyle.bodySmall,
                            color = SuccessGreen
                        )
                    }
                    Spacer(modifier = Modifier.weight(1f))
                    Button(
                        onClick = onSaveServer,
                        modifier = Modifier.height(TouchTarget.comfortable)
                    ) {
                        Text("Save & Connect")
                    }
                }
            }

            // ── Appearance Section ───────────────────────────────────────────
            SettingsSection(title = "Appearance") {
                var darkMode by remember { mutableStateOf(false) }
                SettingsRow(
                    icon = Icons.Default.DarkMode,
                    title = "Dark Mode",
                    subtitle = "Follow system setting",
                    trailing = {
                        Switch(
                            checked = darkMode,
                            onCheckedChange = { darkMode = it }
                        )
                    }
                )
            }

            // ── Data Section ─────────────────────────────────────────────────
            SettingsSection(title = "Data & Storage") {
                SettingsRow(
                    icon = Icons.Default.Storage,
                    title = "Cache Size",
                    subtitle = "124 MB",
                    onClick = {}
                )
                SettingsRow(
                    icon = Icons.Default.DeleteForever,
                    title = "Clear Cache",
                    subtitle = "Free up storage space",
                    onClick = {}
                )
            }

            // ── About Section ───────────────────────────────────────────────
            SettingsSection(title = "About") {
                SettingsRow(
                    icon = Icons.Default.Info,
                    title = "Version",
                    subtitle = "0.1.0 (Build 11)",
                    onClick = {}
                )
                SettingsRow(
                    icon = Icons.Default.Code,
                    title = "Open Source Licenses",
                    subtitle = "Third-party libraries",
                    onClick = {}
                )
            }
        }
    }
}

@Composable
private fun SettingsSection(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    Column {
        Text(
            text = title,
            style = AtomicTextStyle.cardTitle,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.padding(bottom = Spacing.xs)
        )
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(Radius.card),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant
            )
        ) {
            Column(
                modifier = Modifier.padding(Padding.card),
                content = content
            )
        }
    }
}

@Composable
private fun SettingsRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String? = null,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .then(
                if (onClick != null) Modifier.padding(vertical = Spacing.xxs) else Modifier
            ),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(IconSize.xxs),
            tint = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.width(Spacing.sm))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = AtomicTextStyle.body,
                color = MaterialTheme.colorScheme.onSurface
            )
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = AtomicTextStyle.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (trailing != null) trailing()
        else if (onClick != null) {
            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                modifier = Modifier.size(IconSize.xxs),
                tint = MaterialTheme.colorScheme.outline
            )
        }
    }
}