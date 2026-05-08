package com.atomic.app.data.api

import com.atomic.app.data.api.dto.*
import retrofit2.http.*

interface KomgaApi {
    // Server
    @GET("api/v1/servers/me")
    suspend fun getServer(): ServerDto

    // Libraries
    @GET("api/v1/libraries")
    suspend fun getLibraries(): List<LibraryDto>

    @GET("api/v1/libraries/{id}")
    suspend fun getLibrary(@Path("id") id: String): LibraryDto

    // Series
    @GET("api/v1/libraries/{libraryId}/series")
    suspend fun getSeries(@Path("libraryId") libraryId: String): List<SeriesDto>

    @GET("api/v1/series/{id}")
    suspend fun getSeriesById(@Path("id") id: String): SeriesDto

    // Books
    @GET("api/v1/series/{seriesId}/books")
    suspend fun getBooks(@Path("seriesId") seriesId: String): List<BookDto>

    @GET("api/v1/books/{id}")
    suspend fun getBook(@Path("id") id: String): BookDto

    @GET("api/v1/books/{id}/content")
    suspend fun getBookContent(@Path("id") id: String): BookContentDto

    // Read progress
    @GET("api/v1/books/{id}/progress")
    suspend fun getReadProgress(@Path("id") id: String): ReadProgressDto?

    @PUT("api/v1/books/{id}/progress")
    suspend fun updateReadProgress(@Path("id") id: String, @Body progress: UpdateProgressDto)

    // Collections
    @GET("api/v1/collections")
    suspend fun getCollections(): List<CollectionDto>
}