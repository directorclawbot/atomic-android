package com.atomic.app.data.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "books")
data class BookEntity(
    @PrimaryKey val id: String,
    val seriesId: String,
    val name: String,
    val number: Int?,
    val coverUrl: String?,
    val currentPage: Int = 0,
    val totalPages: Int = 0,
    val isDownloaded: Boolean = false
)