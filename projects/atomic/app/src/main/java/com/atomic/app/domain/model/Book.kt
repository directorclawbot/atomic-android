package com.atomic.app.domain.model

data class Book(
    val id: String,
    val title: String,
    val seriesId: String,
    val number: Int,
    val coverUrl: String? = null,
    val currentPage: Int = 0,
    val totalPages: Int = 0,
    val readStatus: ReadStatus = ReadStatus.NOT_STARTED
)