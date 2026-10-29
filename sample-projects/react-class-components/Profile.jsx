import React, { Component } from "react";

export default class Profile extends Component {
  state = { editing: false, name: "Ada" };

  toggle = () => {
    this.setState({ editing: !this.state.editing });
  };

  rename = (event) => {
    this.setState({ name: event.target.value, editing: false });
  };

  render() {
    const { title } = this.props;
    return (
      <section>
        <h2>{title}</h2>
        <p>Don't forget: {this.state.name}</p>
        <button onClick={this.toggle}>{this.state.editing ? "Done" : "Edit"}</button>
        <input value={this.state.name} onChange={this.rename} />
      </section>
    );
  }
}
