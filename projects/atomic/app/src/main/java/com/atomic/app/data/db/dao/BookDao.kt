package com.atomic.app.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.atomic.app.data.db.entity.BookEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface BookDao {
    @Query("SELECT * FROM books WHERE seriesId = :seriesId")
    fun getBooksBySeries(seriesId: String): Flow<List<BookEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertBooks(books: List<BookEntity>)

    @Query("UPDATE books SET currentPage = :page WHERE id = :bookId")
    suspend fun updateReadProgress(bookId: String, page: Int)
}