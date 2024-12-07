import React, { useState, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { PageActions, MediaPageActions, PlaylistPageActions } from '../../utils/actions/';
import { MediaPageStore, PlaylistPageStore } from '../../utils/stores/';
import { addClassname, removeClassname } from '../../utils/helpers/';

import './PlaylistForm.scss';

export function PlaylistCreationForm(props) {
  const nameRef = useRef(null);
  const nameInputRef = useRef(null);

  const descriptionRef = useRef(null);
  const descriptionInputRef = useRef(null);

  const categoryRef = useRef(null);
  const categoryInputRef = useRef(null);
  const [playlistcategory, setPlaylistCategory] = useState('');
  const [categories, setCategories] = useState([]);

  const coverImg = useRef(null);
  const coverImgInputRef = useRef(null);

  const [playlistCover, setPlaylistCover] = useState(null);
  const [errorCoverUploading, setErrorCoverUploading] = useState(null);

  const [id, setId] = useState(props.id || null);
  const [title, setTitle] = useState(props.id ? PlaylistPageStore.get('title') : '');
  const [description, setDescription] = useState(props.id ? PlaylistPageStore.get('description') : '');
  const [descriptionLineHeight, setDescriptionLineHeight] = useState(-1);
  /*const [ selectedPrivacy, setSelectedPrivacy ] = useState( 'public' );*/

  function onFocusDescription() {
    addClassname(descriptionRef.current, 'focused');
  }
  function onBlurDescription() {
    removeClassname(descriptionRef.current, 'focused');
  }
  function onChangePlaylistNameInput() {
    removeClassname(nameRef.current, 'invalid');
  }
  function onFocusPlaylistNameInput() {
    addClassname(nameRef.current, 'focused');
  }
  function onBlurPlaylistNameInput() {
    removeClassname(nameRef.current, 'focused');
  }

  function onChangeTitle() {
    setTitle(nameInputRef.current.value);
  }

  /*function onPrivacyChoose(e){
    setSelectedPrivacy(e.currentTarget.value);
  }*/

  function onChangeDescription() {
    descriptionInputRef.current.style.height = '';

    const contentHeight = descriptionInputRef.current.scrollHeight - 2;
    const contentLineHeight =
      0 < descriptionLineHeight
        ? descriptionLineHeight
        : parseFloat(window.getComputedStyle(descriptionInputRef.current).lineHeight);

    descriptionInputRef.current.style.height =
      3 + Math.max(21, contentLineHeight * Math.floor(contentHeight / contentLineHeight)) + 'px';

    setDescriptionLineHeight(contentLineHeight);
    setDescription(descriptionInputRef.current.value);
  }

  function onClickPlaylistCreate() {
    let title = nameInputRef.current.value.trim();

    if ('' !== title) {
      let description = descriptionInputRef.current.value.trim();

      const body = {          
        title: title,
        description: description,
        // privacy: selectedPrivacy,
      }

      if (id) {
        if (playlistCover) {
          const formData = new FormData();
          formData.append("file", playlistCover);
          PlaylistPageActions.uploadPlaylistCover(formData);
        }
        if (playlistcategory){
          body.type = "set_category";
          body.category = playlistcategory;
        }
        PlaylistPageActions.updatePlaylist(body);
      } else {
        MediaPageActions.createPlaylist({
          title: title,
          description: description,
          // privacy: selectedPrivacy,
        });
      }
    } else {
      addClassname(nameRef.current, 'invalid');
    }
  }

  function playlistCreationCompleted(new_playlist_data) {
    // FIXME: Without delay creates conflict [ Uncaught Error: Dispatch.dispatch(...): Cannot dispatch in the middle of a dispatch. ].

    setTimeout(function () {
      PageActions.addNotification('Playlist created', 'playlistCreationCompleted');
      const plistData = {
        playlist_id: (function (_url_) {
          let ret = _url_.split('/');
          return 1 < ret.length ? ret[ret.length - 1] : null;
        })(new_playlist_data.url),
        add_date: new_playlist_data.add_date,
        description: new_playlist_data.description,
        title: new_playlist_data.title,
        media_list: [],
      };

      props.onPlaylistSave(plistData);
    }, 100);
  }

  function playlistCreationFailed() {
    // FIXME: Without delay creates conflict [ Uncaught Error: Dispatch.dispatch(...): Cannot dispatch in the middle of a dispatch. ].
    setTimeout(function () {
      PageActions.addNotification('Playlist creation failed', 'playlistCreationFailed');
    }, 100);
  }

  function onCancelPlaylistCreation() {
    props.onCancel();
  }

 function playlistCategories (categoriesData) {
    setTimeout(function () {
      setCategories(categoriesData);
    }, 100);
  }

  useEffect(() => {
    MediaPageStore.on('playlist_creation_completed', playlistCreationCompleted);
    MediaPageStore.on('playlist_creation_failed', playlistCreationFailed);
    nameInputRef.current.focus();
    
    PlaylistPageActions.getPlaylistCategory();
    PlaylistPageStore.on('playlist_Categories', playlistCategories);
    return () => {
      MediaPageStore.removeListener('playlist_creation_completed', playlistCreationCompleted);
      MediaPageStore.removeListener('playlist_creation_failed', playlistCreationFailed);
      PlaylistPageStore.removeListener('playlist_Categories', playlistCategories);
    };
  }, []);

  function onSelectCategory(ev) {
    setPlaylistCategory(ev.currentTarget.value);
  }

  const handlePlaylistCover = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) { // 10 MB limit
        PageActions.addNotification("File size should be less than 10 MB.");
        setErrorCoverUploading("File size should be less than 10 MB.");
        return;
      }
      setPlaylistCover(file);
      setErrorCoverUploading(null);
    }
  }


  return (
    <div className="playlist-form-wrap">
      <div className="playlist-form-field playlist-title" ref={nameRef}>
        <span className="playlist-form-label">Title</span>
        <input
          ref={nameInputRef}
          type="text"
          placeholder="Enter playlist title..."
          value={title}
          onChange={onChangeTitle}
          onFocus={onFocusPlaylistNameInput}
          onBlur={onBlurPlaylistNameInput}
          onClick={onChangePlaylistNameInput}
        />
      </div>

      <div className="playlist-form-field playlist-description" ref={descriptionRef}>
        <span className="playlist-form-label">Description</span>
        <textarea
          ref={descriptionInputRef}
          rows="1"
          placeholder="Enter playlist description..."
          value={description}
          onChange={onChangeDescription}
          onFocus={onFocusDescription}
          onBlur={onBlurDescription}
        ></textarea>
      </div>

      {id && 
      <div> 
        <div className="playlist-form-field" ref={categoryRef}>
          <span className="playlist-form-label">Category</span>
          <select value={playlistcategory} onChange={onSelectCategory} ref={categoryInputRef}>
            <option value="" disabled>
              Select a category
            </option>
            {categories?.map((category, index) => (
            <option key={index} value={category?.title}>
              {category?.title}
            </option>
            ))}
          </select>
        </div>

        <div className="playlist-form-field" ref={coverImg}>
          <span className="playlist-form-label">PlayList Cover Image</span>
          <input type="file" name="plalist_cover" accept="image/*" id="plalist_cover" ref={coverImgInputRef} onChange={handlePlaylistCover}/>
          {errorCoverUploading && <p style={{ color: "red" }}>{errorCoverUploading}</p>}
        </div>
      </div>}

      {/*<div className="playlist-form-field playlist-privacy">
					<span className="playlist-form-label">Privacy</span>
					<label><input ref="privacyValue" type="radio" name="privacy" value="public" checked={ 'public' === selectedPrivacy } onChange={ onPrivacyChoose } /><span>Public</span></label>
					<label><input ref="privacyValue" type="radio" name="privacy" value="unlisted" checked={ 'unlisted' === selectedPrivacy } onChange={ onPrivacyChoose } /><span>Unlisted</span></label>
					<label><input ref="privacyValue" type="radio" name="privacy" value="private" checked={ 'private' === selectedPrivacy } onChange={ onPrivacyChoose } /><span>Private</span></label>
				</div>*/}

      <div className="playlist-form-actions">
        <button className="cancel-btn" onClick={onCancelPlaylistCreation}>
          CANCEL
        </button>
        <button className="create-btn" onClick={onClickPlaylistCreate}>
          {id ? 'UPDATE' : 'CREATE'}
        </button>
      </div>
    </div>
  );
}

PlaylistCreationForm.propTypes = {
  id: PropTypes.string,
  onCancel: PropTypes.func.isRequired,
  onPlaylistSave: PropTypes.func.isRequired,
};
