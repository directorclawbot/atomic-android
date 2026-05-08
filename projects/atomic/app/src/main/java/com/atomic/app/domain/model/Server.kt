package com.atomic.app.domain.model

data class Server(
    val id: String,
    val url: String,
    val name: String,
    val username: String,
    val libraries: List<Library> = emptyList()
)

data class Library(
    val id: String,
    val name: String,
    val type: LibraryType,
    val seriesCount: Int = 0
)

enum class LibraryType {
    COMIC, MANGA, BOOK, OTHER
}