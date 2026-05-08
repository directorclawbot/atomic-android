package com.atomic.app.di

import android.content.Context
import androidx.room.Room
import com.atomic.app.data.api.KomgaApi
import com.atomic.app.data.db.AtomicDatabase
import com.atomic.app.data.db.dao.BookDao
import com.atomic.app.data.db.dao.LibraryDao
import com.atomic.app.data.db.dao.SeriesDao
import com.atomic.app.data.db.dao.ServerDao
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient, json: Json): Retrofit {
        return Retrofit.Builder()
            .baseUrl("https://placeholder.local/") // Base URL set at runtime
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Provides
    @Singleton
    fun provideKomgaApi(retrofit: Retrofit): KomgaApi {
        return retrofit.create(KomgaApi::class.java)
    }

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AtomicDatabase {
        return Room.databaseBuilder(
            context,
            AtomicDatabase::class.java,
            "atomic_database"
        ).build()
    }

    @Provides
    fun provideServerDao(db: AtomicDatabase): ServerDao = db.serverDao()

    @Provides
    fun provideLibraryDao(db: AtomicDatabase): LibraryDao = db.libraryDao()

    @Provides
    fun provideSeriesDao(db: AtomicDatabase): SeriesDao = db.seriesDao()

    @Provides
    fun provideBookDao(db: AtomicDatabase): BookDao = db.bookDao()
}