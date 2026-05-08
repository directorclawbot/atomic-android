package com.atomic.app.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class ServerDto(
    val id: String,
    val name: String,
    val url: String
)

@Serializable
data class LibraryDto(
    val id: String,
    val name: String,
    val type: String
)

@Serializable
data class SeriesDto(
    val id: String,
    val name: String,
    val libraryId: String,
    val booksCount: Int = 0
)

@Serializable
data class BookDto(
    val id: String,
    val title: String,
    val seriesId: String,
    val number: Int? = null,
    val booksCount: Int = 0
)

@Serializable
data class BookContentDto(
    val url: String,
    val files: List<BookFileDto> = emptyList()
)

@Serializable
data class BookFileDto(
    val url: String,
    val mediaType: String,
    val size: Long
)

@Serializable
data class ReadProgressDto(
    val bookId: String,
    val page: Int,
    val completed: Boolean
)

@Serializable
data class UpdateProgressDto(
    val page: Int,
    val completed: Boolean = false
)

@Serializable
data class CollectionDto(
    val id: String,
    val name: String,
    val seriesIds: List<String> = emptyList()
)