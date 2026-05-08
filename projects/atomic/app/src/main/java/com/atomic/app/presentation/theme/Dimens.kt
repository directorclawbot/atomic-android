package com.atomic.app.presentation.theme

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

// ─── Spacing ────────────────────────────────────────────────────────────────
object Spacing {
    val none = 0.dp
    val hairline = 0.5.dp
    val micro = 2.dp
    val xxxs = 4.dp
    val xxs = 8.dp
    val xs = 12.dp
    val sm = 16.dp
    val md = 20.dp
    val lg = 24.dp
    val xl = 32.dp
    val xxl = 40.dp
    val xxxl = 48.dp
    val huge = 64.dp
    // Alias for Padding.screen (used directly in composables)
    val screen = 16.dp
}

// ─── Padding (alias for semantic use) ────────────────────────────────────────
object Padding {
    val screen = Spacing.sm
    val card = Spacing.sm
    val cardInner = Spacing.xs
    val listItem = Spacing.sm
    val button = Spacing.sm
    val dialog = Spacing.md
    val section = Spacing.lg
    val fab = Spacing.sm
}

// ─── Corner Radius ───────────────────────────────────────────────────────────
object Radius {
    val none = 0.dp
    val hairline = 2.dp
    val micro = 4.dp
    val xxxs = 6.dp
    val xxs = 8.dp
    val xs = 12.dp
    val sm = 16.dp
    val md = 20.dp
    val lg = 24.dp
    val xl = 32.dp
    val full = 9999.dp

    // Semantic aliases
    val card = xxs
    val button = xxs
    val chip = full
    val dialog = xs
    val bottomSheet = lg
    val snackbar = xxs
    val coverThumbnail = xxs
    val coverMedium = xs
    val coverLarge = sm
}

// ─── Icon Sizes ──────────────────────────────────────────────────────────────
object IconSize {
    val micro = 12.dp
    val xxxs = 16.dp
    val xxs = 20.dp
    val xs = 24.dp
    val sm = 32.dp
    val md = 40.dp
    val lg = 48.dp
    val xl = 56.dp
}

// ─── Elevation (Dp shadows) ─────────────────────────────────────────────────
object Elevation {
    val none = 0.dp
    val surface = 1.dp
    val card = 2.dp
    val raised = 4.dp
    val fab = 6.dp
    val dialog = 8.dp
    val bottomSheet = 16.dp
    val tooltip = 24.dp
}

// ─── Touch Targets ──────────────────────────────────────────────────────────
object TouchTarget {
    val min = 48.dp          // Material minimum
    val comfortable = 56.dp  // Atomic preferred
    val large = 64.dp        // Accessibility mode
}

// ─── Grid / Layout ───────────────────────────────────────────────────────────
object Grid {
    val libraryCoverWidth = 120.dp
    val seriesCoverWidth = 140.dp
    val seriesCoverHeight = 200.dp
    val bookCoverWidth = 100.dp
    val bookCoverHeight = 150.dp
    val homeBannerHeight = 160.dp
    val bottomNavHeight = 80.dp
    val toolbarHeight = 56.dp
    val searchBarHeight = 56.dp
}

// ─── Animation ───────────────────────────────────────────────────────────────
object AnimationDuration {
    val instant = 50L
    val fast = 150L
    val normal = 300L
    val slow = 500L
}