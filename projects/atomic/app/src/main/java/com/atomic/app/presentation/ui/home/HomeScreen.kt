package com.atomic.app.presentation.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.atomic.app.domain.model.Server
import com.atomic.app.presentation.components.EmptyScreen
import com.atomic.app.presentation.components.LoadingScreen
import com.atomic.app.presentation.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    server: Server? = null,
    isLoading: Boolean = false,
    error: String? = null,
    onNavigateToLibrary: (String) -> Unit = {},
    onNavigateToSearch: () -> Unit = {},
    onNavigateToSettings: () -> Unit = {},
    onRetry: () -> Unit = {},
    onConnectServer: () -> Unit = {}
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Atomic",
                        style = AtomicTextStyle.screenTitle
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                ),
                actions = {
                    IconButton(onClick = onNavigateToSearch) {
                        Icon(
                            imageVector = Icons.Default.Search,
                            contentDescription = "Search",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    IconButton(onClick = onNavigateToSettings) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            )
        }
    ) { paddingValues ->
        when {
            isLoading -> LoadingScreen(message = "Connecting to server…")
            error != null -> ErrorContent(
                message = error,
                onRetry = onRetry,
                onConnectServer = onConnectServer
            )
            server == null -> NoServerContent(onConnectServer = onConnectServer)
            else -> HomeContent(
                server = server,
                onNavigateToLibrary = onNavigateToLibrary,
                modifier = Modifier.padding(paddingValues)
            )
        }
    }
}

@Composable
private fun HomeContent(
    server: Server,
    onNavigateToLibrary: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(Spacing.screen),
        verticalArrangement = Arrangement.spacedBy(Spacing.lg)
    ) {
        // ── Hero Banner ───────────────────────────────────────────────────
        item {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(Grid.homeBannerHeight)
                    .clip(RoundedCornerShape(Radius.coverMedium))
                    .background(
                        brush = Brush.horizontalGradient(
                            colors = listOf(AtomicGradientStart, AtomicGradientEnd)
                        )
                    )
                    .padding(Spacing.lg),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("⚛", style = MaterialTheme.typography.displayMedium)
                    Spacer(modifier = Modifier.height(Spacing.xxs))
                    Text(
                        "Atomic",
                        style = AtomicTextStyle.appTitle,
                        color = MaterialTheme.colorScheme.surface
                    )
                    Spacer(modifier = Modifier.height(Spacing.micro))
                    Text(
                        server.name,
                        style = AtomicTextStyle.body,
                        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.85f)
                    )
                }
            }
        }

        // ── Quick Stats Row ──────────────────────────────────────────────
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm)
            ) {
                StatCard(
                    icon = Icons.Default.Collections,
                    value = "—",
                    label = "Libraries",
                    modifier = Modifier.weight(1f),
                    onClick = {}
                )
                StatCard(
                    icon = Icons.Default.MenuBook,
                    value = "—",
                    label = "Books",
                    modifier = Modifier.weight(1f),
                    onClick = {}
                )
                StatCard(
                    icon = Icons.Default.Bookmark,
                    value = "—",
                    label = "In Progress",
                    modifier = Modifier.weight(1f),
                    onClick = {}
                )
            }
        }

        // ── Recent Books Section ───────────────────────────────────────────
        item {
            SectionHeader(title = "Continue Reading", onSeeAll = {})
        }
        item {
            EmptyBooksRow(
                message = "No books in progress",
                actionLabel = "Browse Libraries",
                onAction = {}
            )
        }

        // ── Libraries Section ─────────────────────────────────────────────
        item {
            SectionHeader(title = "Your Libraries", onSeeAll = {})
        }
        item {
            EmptyLibrariesRow(onBrowse = {})
        }
    }
}

@Composable
private fun StatCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    value: String,
    label: String,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier.clickable(onClick = onClick),
        shape = RoundedCornerShape(Radius.card),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = Elevation.card)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Padding.card),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(IconSize.xs),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(Spacing.micro))
            Text(
                text = value,
                style = MaterialTheme.typography.headlineSmall,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = label,
                style = AtomicTextStyle.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun SectionHeader(
    title: String,
    onSeeAll: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = title,
            style = AtomicTextStyle.sectionTitle,
            color = MaterialTheme.colorScheme.onSurface
        )
        TextButton(onClick = onSeeAll) {
            Text("See All", style = AtomicTextStyle.bodySmall)
            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                modifier = Modifier.size(IconSize.micro)
            )
        }
    }
}

@Composable
private fun EmptyBooksRow(
    message: String,
    actionLabel: String,
    onAction: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(140.dp),
        shape = RoundedCornerShape(Radius.card),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                Icons.Default.BookmarkBorder,
                contentDescription = null,
                modifier = Modifier.size(IconSize.md),
                tint = MaterialTheme.colorScheme.outline
            )
            Spacer(modifier = Modifier.height(Spacing.xs))
            Text(
                message,
                style = AtomicTextStyle.body,
                color = MaterialTheme.colorScheme.outline
            )
            Spacer(modifier = Modifier.height(Spacing.xs))
            TextButton(onClick = onAction) {
                Text(actionLabel)
            }
        }
    }
}

@Composable
private fun EmptyLibrariesRow(onBrowse: () -> Unit) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(Spacing.sm)
    ) {
        items(3) { index ->
            PlaceholderLibraryCard(index = index, onClick = onBrowse)
        }
    }
}

@Composable
private fun PlaceholderLibraryCard(index: Int, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .width(Grid.libraryCoverWidth)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(Radius.card),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(Padding.card),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(RoundedCornerShape(Radius.coverThumbnail))
                    .background(MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.Collections,
                    contentDescription = null,
                    modifier = Modifier.size(IconSize.md),
                    tint = MaterialTheme.colorScheme.outline
                )
            }
            Spacer(modifier = Modifier.height(Spacing.xs))
            Text(
                text = "Library ${index + 1}",
                style = AtomicTextStyle.bodySmall,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                text = "— books",
                style = AtomicTextStyle.caption,
                color = MaterialTheme.colorScheme.outline
            )
        }
    }
}

@Composable
private fun NoServerContent(onConnectServer: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.CloudOff,
            contentDescription = null,
            modifier = Modifier.size(IconSize.xl),
            tint = MaterialTheme.colorScheme.outline
        )
        Spacer(modifier = Modifier.height(Spacing.lg))
        Text(
            "No Server Connected",
            style = AtomicTextStyle.sectionTitle,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(Spacing.xxs))
        Text(
            "Add a Komga server to start reading",
            style = AtomicTextStyle.body,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(Spacing.xl))
        Button(
            onClick = onConnectServer,
            modifier = Modifier.height(TouchTarget.comfortable)
        ) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(modifier = Modifier.width(Spacing.xs))
            Text("Add Server")
        }
    }
}

@Composable
private fun ErrorContent(
    message: String,
    onRetry: () -> Unit,
    onConnectServer: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.Warning,
            contentDescription = null,
            modifier = Modifier.size(IconSize.xl),
            tint = MaterialTheme.colorScheme.error
        )
        Spacer(modifier = Modifier.height(Spacing.lg))
        Text(
            "Connection Failed",
            style = AtomicTextStyle.sectionTitle,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(Spacing.xxs))
        Text(
            message,
            style = AtomicTextStyle.body,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(Spacing.xl))
        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.sm)) {
            OutlinedButton(
                onClick = onRetry,
                modifier = Modifier.height(TouchTarget.comfortable)
            ) {
                Icon(Icons.Default.Refresh, contentDescription = null)
                Spacer(modifier = Modifier.width(Spacing.xs))
                Text("Retry")
            }
            Button(
                onClick = onConnectServer,
                modifier = Modifier.height(TouchTarget.comfortable)
            ) {
                Icon(Icons.Default.Settings, contentDescription = null)
                Spacer(modifier = Modifier.width(Spacing.xs))
                Text("Settings")
            }
        }
    }
}