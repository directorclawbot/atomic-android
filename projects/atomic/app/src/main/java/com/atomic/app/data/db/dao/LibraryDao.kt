package com.atomic.app.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.atomic.app.data.db.entity.LibraryEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface LibraryDao {
    @Query("SELECT * FROM libraries WHERE serverId = :serverId")
    fun getLibrariesByServer(serverId: String): Flow<List<LibraryEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLibraries(libraries: List<LibraryEntity>)

    @Query("DELETE FROM libraries WHERE serverId = :serverId")
    suspend fun deleteLibrariesByServer(serverId: String)
}