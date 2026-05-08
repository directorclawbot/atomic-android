package com.atomic.app.presentation.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.atomic.app.presentation.ui.home.HomeScreen
import com.atomic.app.presentation.ui.search.SearchScreen
import com.atomic.app.presentation.ui.settings.SettingsScreen

sealed class Screen(val route: String) {
    data object Home : Screen("home")
    data object Search : Screen("search")
    data object Library : Screen("library/{libraryId}") {
        fun createRoute(libraryId: String) = "library/$libraryId"
    }
    data object Series : Screen("series/{seriesId}") {
        fun createRoute(seriesId: String) = "series/$seriesId"
    }
    data object Reader : Screen("reader/{bookId}") {
        fun createRoute(bookId: String) = "reader/$bookId"
    }
    data object Settings : Screen("settings")
}

@Composable
fun AtomicNavHost() {
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = Screen.Home.route
    ) {
        composable(Screen.Home.route) {
            HomeScreen(
                onNavigateToLibrary = { libraryId ->
                    navController.navigate(Screen.Library.createRoute(libraryId))
                },
                onNavigateToSearch = {
                    navController.navigate(Screen.Search.route)
                },
                onNavigateToSettings = {
                    navController.navigate(Screen.Settings.route)
                }
            )
        }

        composable(Screen.Search.route) {
            SearchScreen(
                onNavigateBack = { navController.popBackStack() },
                onSeriesClick = { seriesId ->
                    navController.navigate(Screen.Series.createRoute(seriesId))
                }
            )
        }

        composable(Screen.Library.route) { backStackEntry ->
            val libraryId = backStackEntry.arguments?.getString("libraryId") ?: ""
            PlaceholderScreen(label = "Library: $libraryId")
        }

        composable(Screen.Series.route) { backStackEntry ->
            val seriesId = backStackEntry.arguments?.getString("seriesId") ?: ""
            PlaceholderScreen(label = "Series: $seriesId")
        }

        composable(Screen.Reader.route) { backStackEntry ->
            val bookId = backStackEntry.arguments?.getString("bookId") ?: ""
            PlaceholderScreen(label = "Reader: $bookId")
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                onNavigateBack = { navController.popBackStack() }
            )
        }
    }
}

@Composable
private fun PlaceholderScreen(label: String) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = "$label — coming soon",
            style = MaterialTheme.typography.bodyLarge
        )
    }
}