
CREATE TABLE album_tags (
    album_id integer NOT NULL,
    tag text NOT NULL,
    PRIMARY KEY (album_id, tag),
    FOREIGN KEY (album_id) REFERENCES albums(album_id) ON DELETE CASCADE
);

--
-- Name: albums; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE albums (
    album_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name character varying(500) NOT NULL,
    artist_id integer,
    barcode character varying(20),
    musicbrainz_id uuid,
    release_date date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    musicbrainz_album_id uuid UNIQUE NOT NULL,
    is_musicbrainz_valid boolean DEFAULT true,
    primary_type text,
    secondary_types text[],
    tags text[],
    folder_path text,
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
);

CREATE TABLE artist_relationships (
    artist_id integer NOT NULL,
    related_artist_id integer NOT NULL,
    relationship_type text NOT NULL,
    PRIMARY KEY (artist_id, related_artist_id, relationship_type),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE,
    FOREIGN KEY (related_artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
);


--
-- Name: artist_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE artist_tags (
    artist_id integer NOT NULL,
    tag text NOT NULL,
    PRIMARY KEY (artist_id, tag),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
);


--
-- Name: artists; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE artists (
    artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name character varying(500) NOT NULL,
    musicbrainz_id uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    musicbrainz_artist_id uuid UNIQUE NOT NULL,
    is_musicbrainz_valid boolean DEFAULT true,
    sort_name text,
    type text,
    begin_area text,
    life_span_start date,
    life_span_ended boolean,
    aliases text[],
    life_span_end date,
    wikidata_id character varying(255)
);

--
-- Name: tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id integer,
    key character varying(100) NOT NULL,
    value text NOT NULL,
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

--
-- Name: track_features; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE track_features (
    feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id integer NOT NULL,
    danceability real,
    female real,
    male real,
    genre_alternative real,
    genre_blues real,
    genre_electronic real,
    genre_folkcountry real,
    genre_funksoulrnb real,
    genre_jazz real,
    genre_pop real,
    genre_raphiphop real,
    genre_rock real,
    genre_electronic_ambient real,
    genre_electronic_dnb real,
    genre_electronic_house real,
    genre_electronic_techno real,
    genre_electronic_trance real,
    genre_rosamerica_cla real,
    genre_rosamerica_dan real,
    genre_rosamerica_hip real,
    genre_rosamerica_jaz real,
    genre_rosamerica_pop real,
    genre_rosamerica_rhy real,
    genre_rosamerica_roc real,
    genre_rosamerica_spe real,
    genre_tzanetakis_blu real,
    genre_tzanetakis real,
    genre_tzanetakis_cou real,
    genre_tzanetakis_dis real,
    genre_tzanetakis_hip real,
    genre_tzanetakis_jaz real,
    genre_tzanetakis_met real,
    genre_tzanetakis_pop real,
    genre_tzanetakis_reg real,
    genre_tzanetakis_roc real,
    ismir04_rhythm_chachacha real,
    ismir04_rhythm_jive real,
    ismir04_rhythm_quickstep real,
    ismir04_rhythm_rumba_american real,
    ismir04_rhythm_rumba_international real,
    ismir04_rhythm_rumba_misc real,
    ismir04_rhythm_samba real,
    ismir04_rhythm_tango real,
    ismir04_rhythm_viennesewaltz real,
    ismir04_rhythm_waltz real,
    mood_acoustic real,
    mood_electronic real,
    mood_happy real,
    mood_party real,
    mood_relaxed real,
    mood_sad real,
    moods_mirex real,
    timbre real,
    tonal_atonal real,
    voice_instrumental real,
    average_loudness real,
    dynamic_complexity real,
    bpm real,
    chords_key character varying(10),
    chords_number_rate real,
    chords_scale character varying(10),
    danceability_low real,
    FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
);



--
-- Name: track_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE track_tags (
    track_id integer NOT NULL,
    tag text NOT NULL,
    PRIMARY KEY (track_id, tag),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id) ON DELETE CASCADE
);


--
-- Name: tracks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE tracks (
    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title character varying(500) NOT NULL,
    artist_id integer,
    album_id integer,
    genre character varying(100),
    year date,
    track_number character varying(10),
    path text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    musicbrainz_release_track_id uuid UNIQUE,
    is_musicbrainz_valid boolean DEFAULT true,
    length text DEFAULT 'Unknown',
    recording_id uuid UNIQUE,
    tags text[],
    FOREIGN KEY (album_id) REFERENCES albums(album_id),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
);

