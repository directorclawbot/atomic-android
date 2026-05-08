package com.atomic.app.presentation.ui.search

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.atomic.app.domain.model.Series
import com.atomic.app.domain.model.Book
import com.atomic.app.presentation.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    onNavigateBack: () -> Unit,
    onSeriesClick: (String) -> Unit = {},
    onBookClick: (String) -> Unit = {},
    searchQuery: String = "",
    onSearchQueryChange: (String) -> Unit = {},
    isSearching: Boolean = false,
    results: List<Series> = emptyList(),
    recentSearches: List<String> = emptyList(),
    onClearRecent: () -> Unit = {}
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Search", style = AtomicTextStyle.screenTitle) },
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
        ) {
            // ── Search Bar ────────────────────────────────────────────────
            OutlinedTextField(
                value = searchQuery,
                onValueChange = onSearchQueryChange,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(Spacing.sm),
                placeholder = { Text("Search books & series…") },
                leadingIcon = {
                    Icon(Icons.Default.Search, contentDescription = null)
                },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { onSearchQueryChange("") }) {
                            Icon(Icons.Default.Clear, contentDescription = "Clear")
                        }
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = {}),
                shape = RoundedCornerShape(Radius.button)
            )

            when {
                isSearching -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(IconSize.md))
                    }
                }
                searchQuery.isEmpty() && recentSearches.isNotEmpty() -> {
                    RecentSearches(
                        searches = recentSearches,
                        onSearchClick = onSearchQueryChange,
                        onClear = onClearRecent
                    )
                }
                searchQuery.isNotEmpty() && results.isEmpty() -> {
                    NoResults(query = searchQuery)
                }
                results.isNotEmpty() -> {
                    LazyColumn(
                        contentPadding = PaddingValues(Spacing.screen),
                        verticalArrangement = Arrangement.spacedBy(Spacing.sm)
                    ) {
                        items(results) { series ->
                            SeriesResultCard(
                                series = series,
                                onClick = { onSeriesClick(series.id) }
                            )
                        }
                    }
                }
                else -> {
                    SearchHint()
                }
            }
        }
    }
}

@Composable
private fun RecentSearches(
    searches: List<String>,
    onSearchClick: (String) -> Unit,
    onClear: () -> Unit
) {
    Column(modifier = Modifier.padding(Spacing.screen)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "Recent Searches",
                style = AtomicTextStyle.cardTitle,
                color = MaterialTheme.colorScheme.onSurface
            )
            TextButton(onClick = onClear) {
                Text("Clear", style = AtomicTextStyle.bodySmall)
            }
        }
        Spacer(modifier = Modifier.height(Spacing.xs))
        searches.forEach { query ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSearchClick(query) }
                    .padding(vertical = Spacing.xs),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.History,
                    contentDescription = null,
                    modifier = Modifier.size(IconSize.micro),
                    tint = MaterialTheme.colorScheme.outline
                )
                Spacer(modifier = Modifier.width(Spacing.sm))
                Text(
                    query,
                    style = AtomicTextStyle.body,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}

@Composable
private fun SeriesResultCard(
    series: Series,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(Radius.card),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Padding.card),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Cover thumbnail
            Box(
                modifier = Modifier
                    .size(Grid.bookCoverWidth, Grid.bookCoverHeight)
                    .clip(RoundedCornerShape(Radius.coverThumbnail))
                    .background(
                        MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
                    ),
                contentAlignment = Alignment.Center
            ) {
                if (series.coverUrl != null) {
                    // TODO: Coil image loading via series.coverUrl
                    Icon(
                        Icons.Default.MenuBook,
                        contentDescription = null,
                        modifier = Modifier.size(IconSize.lg),
                        tint = MaterialTheme.colorScheme.outline
                    )
                } else {
                    Icon(
                        Icons.Default.Collections,
                        contentDescription = null,
                        modifier = Modifier.size(IconSize.lg),
                        tint = MaterialTheme.colorScheme.outline
                    )
                }
            }

            Spacer(modifier = Modifier.width(Spacing.sm))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = series.title,
                    style = AtomicTextStyle.body,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                if (series.bookCount > 0) {
                    Spacer(modifier = Modifier.height(Spacing.micro))
                    Text(
                        "${series.bookCount} books",
                        style = AtomicTextStyle.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(modifier = Modifier.height(Spacing.micro))
                Text(
                    "Library: ${series.libraryId}",
                    style = AtomicTextStyle.caption,
                    color = MaterialTheme.colorScheme.outline
                )
            }

            Icon(
                Icons.Default.ChevronRight,
                contentDescription = null,
                modifier = Modifier.size(IconSize.xxs),
                tint = MaterialTheme.colorScheme.outline
            )
        }
    }
}

@Composable
private fun NoResults(query: String) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.SearchOff,
            contentDescription = null,
            modifier = Modifier.size(IconSize.xl),
            tint = MaterialTheme.colorScheme.outline
        )
        Spacer(modifier = Modifier.height(Spacing.lg))
        Text(
            "No results for \"$query\"",
            style = AtomicTextStyle.sectionTitle,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
        Spacer(modifier = Modifier.height(Spacing.xxs))
        Text(
            "Try different keywords or check spelling",
            style = AtomicTextStyle.body,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
    }
}

@Composable
private fun SearchHint() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.Search,
            contentDescription = null,
            modifier = Modifier.size(IconSize.xl),
            tint = MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)
        )
        Spacer(modifier = Modifier.height(Spacing.lg))
        Text(
            "Search your library",
            style = AtomicTextStyle.sectionTitle,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Spacer(modifier = Modifier.height(Spacing.xxs))
        Text(
            "Find books and series by title, author, or genre",
            style = AtomicTextStyle.body,
            color = MaterialTheme.colorScheme.outline,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
    }
}