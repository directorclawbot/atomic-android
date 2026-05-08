package com.atomic.app.domain.model

data class Series(
    val id: String,
    val title: String,
    val libraryId: String,
    val coverUrl: String? = null,
    val bookCount: Int = 0,
    val readStatus: ReadStatus = ReadStatus.NOT_STARTED
)

enum class ReadStatus {
    NOT_STARTED, IN_PROGRESS, COMPLETED
}