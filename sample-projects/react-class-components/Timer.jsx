import React from "react";

class Timer extends React.Component {
  state = { seconds: 0 };

  componentDidMount() {
    this.interval = setInterval(() => this.setState({ seconds: this.state.seconds + 1 }), 1000);
  }

  componentWillUnmount() {
    clearInterval(this.interval);
  }

  render() {
    return <span>{this.state.seconds}s</span>;
  }
}

export default Timer;
