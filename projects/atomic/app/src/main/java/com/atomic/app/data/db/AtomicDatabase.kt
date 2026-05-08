package com.atomic.app.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.atomic.app.data.db.dao.BookDao
import com.atomic.app.data.db.dao.LibraryDao
import com.atomic.app.data.db.dao.SeriesDao
import com.atomic.app.data.db.dao.ServerDao
import com.atomic.app.data.db.entity.BookEntity
import com.atomic.app.data.db.entity.LibraryEntity
import com.atomic.app.data.db.entity.SeriesEntity
import com.atomic.app.data.db.entity.ServerEntity

@Database(
    entities = [ServerEntity::class, LibraryEntity::class, SeriesEntity::class, BookEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AtomicDatabase : RoomDatabase() {
    abstract fun serverDao(): ServerDao
    abstract fun libraryDao(): LibraryDao
    abstract fun seriesDao(): SeriesDao
    abstract fun bookDao(): BookDao
}